"""Fase 1: funções puras do gerador de golden dataset (sem rede, sem disco)."""

import json

import pytest

from ragbench.core.models import QuestionType
from ragbench.evaluation.question_generator import (
    GoldenDatasetGenerator,
    build_user_prompt,
    parse_questions,
    strip_fences,
)


def _payload(*items: dict) -> str:
    return json.dumps({"questions": list(items)}, ensure_ascii=False)


def test_strip_fences_plain_unchanged():
    assert strip_fences('  {"a": 1}  ') == '{"a": 1}'


def test_strip_fences_json_and_uppercase():
    assert strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_fences('```JSON\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_parse_valid_questions_typed():
    raw = _payload(
        {"question": " Q1? ", "question_type": "EDGE_CASE", "ground_truth": " G1 "},
        {"question": "Q2?", "question_type": "ROLE_RESTRICTION", "ground_truth": "G2"},
    )
    out = parse_questions(raw, "pop_x.txt")
    assert len(out) == 2
    assert out[0].question == "Q1?"
    assert out[0].question_type == QuestionType.EDGE_CASE
    assert out[0].ground_truth == "G1"
    assert out[0].source_document == "pop_x.txt"


def test_parse_fenced_and_prefixed_json_via_fallback():
    raw = (
        "Aqui está o resultado:\n```json\n"
        + _payload({"question": "Q?", "question_type": "CONDITIONAL_WORKFLOW", "ground_truth": "G"})
        + "\n```\n"
    )
    out = parse_questions(raw, "pop_y.md")
    assert len(out) == 1
    assert out[0].question_type == QuestionType.CONDITIONAL_WORKFLOW


def test_parse_unknown_type_becomes_unmapped_and_non_dict_skipped():
    raw = _payload(
        {"question": "Q?", "question_type": "TIPO_INVENTADO", "ground_truth": "G"},
        "só uma string",
        42,
    )
    out = parse_questions(raw, "pop_z.txt")
    assert len(out) == 1
    assert out[0].question_type == QuestionType.UNMAPPED


def test_parse_garbage_returns_empty():
    assert parse_questions("sem json aqui", "pop.txt") == []
    assert parse_questions("```json\n{invalido,,,\n```", "pop.txt") == []


def test_build_user_prompt_contains_doc_and_count():
    prompt = build_user_prompt("pop_a.txt", "TEXTO_DO_POP", 3)
    assert "pop_a.txt" in prompt
    assert "TEXTO_DO_POP" in prompt
    assert "3" in prompt


class _FakeLLM:
    def __init__(self, content: str | Exception):
        self.content = content
        self.calls: list[dict] = []

    async def generate_completion(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.content, Exception):
            raise self.content
        return self.content


def _hermetic_settings(monkeypatch, tmp_path):
    import os

    from ragbench.config import BenchmarkSettings

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("OLLAMA__", "LIGHTRAG__", "CHAT__", "RAGAS__")):
            monkeypatch.delenv(key, raising=False)
    return BenchmarkSettings(_env_file=None)


@pytest.mark.asyncio
async def test_generate_for_doc_delegates_to_parse(monkeypatch, tmp_path):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    doc = tmp_path / "pop.txt"
    doc.write_text("conteúdo do pop", encoding="utf-8")
    fake = _FakeLLM(_payload({"question": "Q?", "question_type": "EDGE_CASE", "ground_truth": "G"}))
    gen = GoldenDatasetGenerator(settings=settings, ollama_client=fake)  # type: ignore[arg-type]

    out = await gen.generate_for_doc(doc, questions_per_doc=1)

    assert len(out) == 1
    assert out[0].source_document == "pop.txt"
    assert fake.calls[0]["temperature"] == 0.3


@pytest.mark.asyncio
async def test_generate_for_doc_llm_error_returns_empty(monkeypatch, tmp_path):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    doc = tmp_path / "pop.txt"
    doc.write_text("conteúdo", encoding="utf-8")
    fake = _FakeLLM(RuntimeError("llm down"))
    gen = GoldenDatasetGenerator(settings=settings, ollama_client=fake)  # type: ignore[arg-type]

    assert await gen.generate_for_doc(doc) == []


@pytest.mark.asyncio
async def test_generate_dataset_writes_json_and_filters_empty(monkeypatch, tmp_path):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    in_dir = tmp_path / "pops"
    in_dir.mkdir()
    (in_dir / "a.txt").write_text("pop a", encoding="utf-8")
    (in_dir / "b.md").write_text("pop b", encoding="utf-8")
    fake = _FakeLLM(_payload({"question": "Q?", "question_type": "EDGE_CASE", "ground_truth": "G"}))
    gen = GoldenDatasetGenerator(settings=settings, ollama_client=fake)  # type: ignore[arg-type]

    out_file = tmp_path / "out" / "golden.json"
    dataset = await gen.generate_dataset(
        input_dir=in_dir, output_file=out_file, questions_per_doc=1
    )

    assert len(dataset) == 2
    assert out_file.exists()
    assert len(json.loads(out_file.read_text(encoding="utf-8"))) == 2


@pytest.mark.asyncio
async def test_generate_dataset_empty_dir(monkeypatch, tmp_path):
    settings = _hermetic_settings(monkeypatch, tmp_path)
    in_dir = tmp_path / "vazia"
    in_dir.mkdir()
    fake = _FakeLLM(_payload())
    gen = GoldenDatasetGenerator(settings=settings, ollama_client=fake)  # type: ignore[arg-type]

    assert await gen.generate_dataset(input_dir=in_dir, output_file=tmp_path / "o.json") == []


@pytest.mark.asyncio
async def test_generate_dataset_respects_concurrency(monkeypatch, tmp_path):
    import asyncio

    settings = _hermetic_settings(monkeypatch, tmp_path)
    in_dir = tmp_path / "pops"
    in_dir.mkdir()
    for name in ("a.txt", "b.md", "c.txt"):
        (in_dir / name).write_text(f"pop {name}", encoding="utf-8")

    class _TrackingLLM(_FakeLLM):
        def __init__(self):
            super().__init__(
                _payload({"question": "Q?", "question_type": "EDGE_CASE", "ground_truth": "G"})
            )
            self.in_flight = 0
            self.max_seen = 0

        async def generate_completion(self, **kwargs):
            self.in_flight += 1
            self.max_seen = max(self.max_seen, self.in_flight)
            try:
                await asyncio.sleep(0.01)
                return await super().generate_completion(**kwargs)
            finally:
                self.in_flight -= 1

    fake = _TrackingLLM()
    gen = GoldenDatasetGenerator(settings=settings, ollama_client=fake)  # type: ignore[arg-type]

    dataset = await gen.generate_dataset(
        input_dir=in_dir, output_file=tmp_path / "o.json", concurrency=1
    )
    assert len(dataset) == 3
    assert fake.max_seen == 1  # serializado pelo semaphore
