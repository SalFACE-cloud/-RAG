import json
import logging
from typing import Optional

import httpx

from configs.prompts import build_user_prompt, get_system_prompt
from configs.settings import LLM_API_BASE, LLM_API_KEY, LLM_MODEL
from services.indexer.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)

LLM_NOT_CONFIGURED = "未配置 LLM_API_BASE / LLM_API_KEY，请先在 .env 中填写。"


class RAGAnswerGenerator:
    def __init__(self, retriever: Optional[HybridRetriever] = None):
        self.retriever = retriever or HybridRetriever()

    @staticmethod
    def is_llm_configured() -> bool:
        return bool(LLM_API_BASE and LLM_API_KEY)

    def retrieve_context(
        self,
        question: str,
        subject: Optional[str] = None,
        top_k: int = 20,
        top_n: int = 5,
    ) -> tuple[list[dict], str]:
        context_results = self.retriever.hybrid_search(
            query=question,
            subject=subject,
            top_k=top_k,
            top_n=top_n,
        )
        context_text = "\n\n---\n\n".join(
            f"[来源: {r['source_file']} > {r['section_title']}]\n{r['content']}"
            for r in context_results
        )
        return context_results, context_text

    def build_prompts(
        self,
        question: str,
        context_text: str,
        subject: Optional[str] = None,
        student_level: Optional[str] = None,
    ) -> tuple[str, str]:
        system_prompt = get_system_prompt(subject)
        user_prompt = build_user_prompt(
            question=question,
            context_text=context_text,
            student_level=student_level,
            subject=subject,
        )
        return system_prompt, user_prompt

    def generate_answer_sync(
        self,
        question: str,
        subject: Optional[str] = None,
        student_level: Optional[str] = None,
        top_k: int = 20,
        top_n: int = 5,
    ) -> dict:
        context_results, context_text = self.retrieve_context(
            question, subject=subject, top_k=top_k, top_n=top_n
        )
        system_prompt, user_prompt = self.build_prompts(
            question, context_text, subject=subject, student_level=student_level
        )
        if not self.is_llm_configured():
            return {
                "answer": LLM_NOT_CONFIGURED,
                "chunks": context_results,
                "llm_ok": False,
                "generation_skipped": True,
            }
        try:
            answer = self._call_llm_sync(system_prompt, user_prompt)
            return {
                "answer": answer,
                "chunks": context_results,
                "llm_ok": True,
                "generation_skipped": False,
            }
        except Exception as exc:
            logger.warning("LLM 调用失败: %s", exc)
            return {
                "answer": f"LLM 调用失败: {exc}",
                "chunks": context_results,
                "llm_ok": False,
                "generation_skipped": False,
            }

    async def generate_answer(
        self,
        question: str,
        subject: Optional[str] = None,
        student_level: Optional[str] = None,
        top_k: int = 20,
        top_n: int = 5,
    ) -> dict:
        context_results, context_text = self.retrieve_context(
            question, subject=subject, top_k=top_k, top_n=top_n
        )
        system_prompt, user_prompt = self.build_prompts(
            question, context_text, subject=subject, student_level=student_level
        )
        if not self.is_llm_configured():
            return {
                "answer": LLM_NOT_CONFIGURED,
                "chunks": context_results,
                "llm_ok": False,
                "generation_skipped": True,
            }
        try:
            answer = await self._call_llm_async(system_prompt, user_prompt)
            return {
                "answer": answer,
                "chunks": context_results,
                "llm_ok": True,
                "generation_skipped": False,
            }
        except Exception as exc:
            logger.warning("LLM 调用失败: %s", exc)
            return {
                "answer": f"LLM 调用失败: {exc}",
                "chunks": context_results,
                "llm_ok": False,
                "generation_skipped": False,
            }

    async def stream_llm_events(self, system_prompt: str, user_prompt: str):
        if not self.is_llm_configured():
            for ch in LLM_NOT_CONFIGURED:
                yield {"type": "token", "content": ch}
            return

        headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{LLM_API_BASE.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        yield {"type": "token", "content": delta}

    def _call_llm_sync(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0.2,
        }
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{LLM_API_BASE.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_llm_async(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{LLM_API_BASE.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
