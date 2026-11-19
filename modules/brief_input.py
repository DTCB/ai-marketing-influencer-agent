from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from .brief_parsing import EXAMPLE_SENTENCE, ParsedBrief, build_brief_prompt, parse_brief_response
from .llm_client import generate_with_optional_llm, get_llm_config


_TEXT = "brief_input_sentence"
_PREVIEW = "brief_input_preview"
_WIDGET_PREFIX = "_brief_input_"


def reset_brief_input() -> None:
    for key in list(st.session_state):
        if key in (_TEXT, _PREVIEW) or key.startswith(_WIDGET_PREFIX):
            del st.session_state[key]


def _start_preview(brief: dict, parsed: ParsedBrief, source: str, error: str | None = None) -> None:
    for key in list(st.session_state):
        if key.startswith(f"{_WIDGET_PREFIX}preview_"):
            del st.session_state[key]
    st.session_state[_PREVIEW] = {
        "budget": brief["budget_total"] if parsed.budget is None else parsed.budget,
        "count": brief["expected_creator_count"] if parsed.count is None else parsed.count,
        "tone": parsed.tone or "none",
        "continued_fields": tuple(
            label for label, value in (("预算", parsed.budget), ("人数", parsed.count)) if value is None
        ),
        "uncertainties": parsed.uncertainties,
        "source": source,
        "error": error,
    }


def _load_example(brief: dict) -> None:
    st.session_state[_TEXT] = EXAMPLE_SENTENCE
    st.session_state[f"{_WIDGET_PREFIX}sentence"] = EXAMPLE_SENTENCE
    _start_preview(brief, ParsedBrief(50_000, 5, "gentle"), "本地示例")


def _parse_sentence(brief: dict, sentence: str) -> None:
    if not sentence:
        st.warning("请先填写一句话 Brief。")
        return
    with st.spinner("正在提取投放条件…"):
        result = generate_with_optional_llm(build_brief_prompt(sentence), lambda: "")
    if not result.used_llm:
        _start_preview(brief, ParsedBrief(), "手动编辑", result.error or "暂时无法解析。")
        return
    try:
        parsed = parse_brief_response(result.content)
    except ValueError:
        _start_preview(brief, ParsedBrief(), "手动编辑", "解析结果格式异常。")
    else:
        _start_preview(brief, parsed, "模型解析")


def _save_preview_field(field: str, widget_key: str) -> None:
    st.session_state[_PREVIEW][field] = st.session_state[widget_key]


def _preview_widget(field: str, default: int | str | bool) -> dict:
    key = f"{_WIDGET_PREFIX}preview_{field}"
    st.session_state.setdefault(key, st.session_state[_PREVIEW].get(field, default))
    return {"key": key, "on_change": _save_preview_field, "args": (field, key)}


def _render_tone_evidence(creators: pd.DataFrame, excluded_ids: set[str]) -> set[str]:
    suggested_exclusions = set()
    remarks = creators["risk_note"].fillna("")
    evidence = creators.loc[remarks.str.contains("调性温和|风格尖锐", regex=True)]
    if evidence.empty:
        st.caption("当前档案暂无可用于核对温和调性的备注。")
    for creator in evidence.itertuples(index=False):
        st.write(f"**{creator.creator_name}**　{creator.risk_note}")
        if "风格尖锐" not in creator.risk_note:
            continue
        if creator.creator_id in excluded_ids:
            st.caption("已列为本轮暂不合作。")
        else:
            st.checkbox(
                f"本轮暂不合作 · {creator.creator_name}",
                **_preview_widget(f"exclude_{creator.creator_id}", False),
            )
            suggested_exclusions.add(creator.creator_id)
    return suggested_exclusions


def _apply_preview(
    suggested_exclusions: set[str],
    on_apply: Callable[[int, int, set[str]], None],
) -> None:
    exclusions = set()
    if st.session_state[f"{_WIDGET_PREFIX}preview_tone"] == "gentle":
        exclusions = {
            creator_id for creator_id in suggested_exclusions
            if st.session_state.get(f"{_WIDGET_PREFIX}preview_exclude_{creator_id}")
        }
    on_apply(
        st.session_state[f"{_WIDGET_PREFIX}preview_budget"],
        st.session_state[f"{_WIDGET_PREFIX}preview_count"],
        exclusions,
    )
    for creator_id in exclusions:
        field = f"exclude_{creator_id}"
        st.session_state[_PREVIEW][field] = False
        st.session_state[f"{_WIDGET_PREFIX}preview_{field}"] = False


def render_brief_input(
    brief: dict,
    creators: pd.DataFrame,
    excluded_ids: set[str],
    on_apply: Callable[[int, int, set[str]], None],
) -> None:
    with st.expander("用一句话调整方案"):
        text_key = f"{_WIDGET_PREFIX}sentence"
        st.session_state.setdefault(text_key, st.session_state.get(_TEXT, ""))
        sentence = st.text_input(
            "一句话 Brief",
            placeholder=EXAMPLE_SENTENCE,
            key=text_key,
            on_change=lambda: st.session_state.update({_TEXT: st.session_state[text_key]}),
        ).strip()
        model_available = get_llm_config().enabled
        if not model_available:
            st.caption("模型未配置，可以载入示例或手动编辑。")
        if st.button("解析 Brief", disabled=not model_available):
            _parse_sentence(brief, sentence)

        example, manual = st.columns(2)
        example.button("载入示例", on_click=_load_example, args=(brief,))
        manual.button("手动编辑", on_click=_start_preview, args=(brief, ParsedBrief(), "手动编辑"))

        preview = st.session_state.get(_PREVIEW)
        if preview is None:
            return
        if preview["error"]:
            st.warning(f"{preview['error']} 可继续手动编辑或载入示例。")
        st.caption(f"{preview['source']} · 应用前请确认投放条件")
        if preview["source"] == "模型解析" and preview["continued_fields"]:
            st.caption(f"{'和'.join(preview['continued_fields'])}沿用当前值，可在下方修改。")
        for note in preview["uncertainties"]:
            st.text(f"待确认 · {note}")

        st.number_input("预览预算（元）", min_value=0, step=1000, **_preview_widget("budget", 0))
        st.number_input("预览合作人数", min_value=1, step=1, **_preview_widget("count", 1))
        tone = st.selectbox(
            "预览内容调性",
            ["none", "gentle"],
            format_func={"none": "未指定", "gentle": "偏好温和表达"}.get,
            **_preview_widget("tone", "none"),
        )
        suggested_exclusions = set()
        if tone == "gentle":
            platform_creators = creators.loc[creators["platform"].eq(brief["preferred_platform"])]
            suggested_exclusions = _render_tone_evidence(platform_creators, excluded_ids)
        st.button("应用并重算", on_click=_apply_preview, args=(suggested_exclusions, on_apply))
