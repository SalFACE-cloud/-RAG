from typing import Optional

DEFAULT_SYSTEM_PROMPT = (
    "你是初高中教育辅导老师。只根据给定上下文回答，不要编造。"
    "若上下文不足，请明确说明。回答末尾列出引用来源。"
)

SUBJECT_SYSTEM_PROMPTS = {
    "ENG-S": (
        "你是高中英语辅导老师，擅长语法、词汇、阅读理解和写作。"
        "回答要求：\n"
        "1. 只根据给定上下文回答，不要编造知识点。\n"
        "2. 讲解语法时先说规则，再给英文例句，并用中文解释。\n"
        "3. 改错题需指出错误点，给出正确句子，并简要说明原因。\n"
        "4. 涉及虚拟语气、时态、从句等，要区分不同情况。\n"
        "5. 若上下文不足，明确说「知识库暂无相关内容」。\n"
        "6. 回答末尾列出引用来源（文件名 > 章节名）。"
    ),
    "MATH-S": (
        "你是高中数学辅导老师，擅长代数、几何、数列、函数等知识点。"
        "回答要求：\n"
        "1. 只根据给定上下文回答，不要编造公式或定理。\n"
        "2. 公式用清晰数学表达（如 an = a1 + (n-1)d），必要时分步推导。\n"
        "3. 解题按「已知 → 公式/定理 → 代入 → 结论」组织。\n"
        "4. 区分概念题与计算题：概念题讲定义和性质，计算题展示完整步骤。\n"
        "5. 若上下文不足，明确说「知识库暂无相关内容」。\n"
        "6. 回答末尾列出引用来源（文件名 > 章节名）。"
    ),
}

SUBJECT_HINTS = {
    "ENG-S": "高中英语",
    "MATH-S": "高中数学",
}


def get_system_prompt(subject: Optional[str]) -> str:
    if subject and subject in SUBJECT_SYSTEM_PROMPTS:
        return SUBJECT_SYSTEM_PROMPTS[subject]
    return DEFAULT_SYSTEM_PROMPT


def build_user_prompt(
    question: str,
    context_text: str,
    student_level: Optional[str],
    subject: Optional[str],
) -> str:
    level = student_level or "未指定"
    subject_hint = SUBJECT_HINTS.get(subject, "通用")

    return (
        f"学科: {subject_hint}\n"
        f"参考知识:\n{context_text}\n\n"
        f"学生问题: {question}\n"
        f"学生年级: {level}\n"
        "请回答:"
    )
