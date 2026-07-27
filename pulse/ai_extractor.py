"""
pulse/ai_extractor.py — LLM 增强的职位解析 (可选)

当 API key 可用时:
  - extract_skills(): Claude/GPT 从 JD 描述提取技能列表
  - generate_summary(): 职位一句话总结
  - classify_jd(): LLM 分类 (超越正则匹配)

无 API key 时静默降级, 不阻断管道。
"""
import json, os, logging
from typing import Optional

logger = logging.getLogger("pulse.ai_extractor")


def _get_client():
    """获取 LLM 客户端 (OpenAI 兼容接口)"""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            return ("anthropic", Anthropic(api_key=api_key))
        except ImportError:
            logger.warning("anthropic 包未安装")
            return None
    else:
        try:
            from openai import OpenAI
            return ("openai", OpenAI(api_key=api_key))
        except ImportError:
            logger.warning("openai 包未安装")
            return None


def extract_skills(job_title: str, description: str = "") -> list[str]:
    """用 LLM 从职位描述提取技能列表

    无 API key 时回退到关键词匹配。
    """
    client = _get_client()
    if client is None:
        # Fallback: keyword-based extraction
        return _fallback_skills(job_title)

    try:
        provider, cl = client
        text = f"职位: {job_title}\n描述: {description[:2000]}"
        prompt = """从这个职位描述中提取技能列表。返回 JSON 数组格式。
只返回 JSON, 不要其他文字。例如: ["Python", "机器学习", "SQL"]"""

        if provider == "anthropic":
            resp = cl.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
            )
            skills = json.loads(resp.content[0].text)
        else:
            resp = cl.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
                max_tokens=300,
            )
            skills = json.loads(resp.choices[0].message.content)

        return skills if isinstance(skills, list) else []
    except Exception as e:
        logger.warning(f"LLM extract_skills failed: {e}")
        return _fallback_skills(job_title)


def generate_summary(job_title: str, description: str = "") -> str:
    """生成 50 字以内职位总结"""
    client = _get_client()
    if client is None:
        return job_title

    try:
        provider, cl = client
        text = f"职位: {job_title}\n描述: {description[:2000]}"
        prompt = "用 30 字以内总结这个职位, 中文。"

        if provider == "anthropic":
            resp = cl.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
            )
            return resp.content[0].text.strip()
        else:
            resp = cl.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
                max_tokens=100,
            )
            return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"LLM generate_summary failed: {e}")
        return job_title


def _fallback_skills(job_title: str) -> list[str]:
    """无 LLM 时的关键词回退"""
    keyword_map = {
        "AI": ["机器学习", "深度学习", "NLP"],
        "算法": ["机器学习", "数学建模"],
        "数据": ["SQL", "Python", "ETL"],
        "后端": ["Python", "Java", "Go"],
        "前端": ["React", "Vue", "TypeScript"],
        "运维": ["Docker", "K8s", "CI/CD"],
        "产品": ["需求分析", "项目管理"],
        "管理": ["团队管理", "架构设计"],
    }
    skills = []
    for kw, skill_list in keyword_map.items():
        if kw in job_title:
            skills.extend(skill_list)
    return skills or ["通用"]
