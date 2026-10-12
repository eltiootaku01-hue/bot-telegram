# -*- coding: utf-8 -*-
"""Structured analysis results and a safe, declarative numeric simulator."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any


class SimulationInputError(ValueError):
    """A simulation payload violates the declarative input contract."""


@dataclass(frozen=True, slots=True)
class SimulationResult:
    status: str
    scenarios: tuple[dict[str, Any], ...]
    text: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "scenarios": list(self.scenarios), "error": self.error}


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    objective: str
    content_analyzed: str
    evidence_available: bool
    evidence_references: tuple[str, ...]
    evidence_status: str
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    alternatives: tuple[str, ...]
    risks: tuple[str, ...]
    recommendation: str
    next_action: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "content_analyzed": self.content_analyzed,
            "evidence_available": self.evidence_available,
            "evidence_references": list(self.evidence_references),
            "evidence_status": self.evidence_status,
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "alternatives": list(self.alternatives),
            "risks": list(self.risks),
            "recommendation": self.recommendation,
            "next_action": self.next_action,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    status: str
    text: str
    report: AnalysisReport | None = None
    error_code: str | None = None

    @classmethod
    def unavailable(cls, reason: str) -> "AnalysisResult":
        messages = {
            "provider_unavailable": "No se completó el análisis: el proveedor configurado no está disponible o devolvió un error.",
            "invalid_analysis_input": "No se ejecutó el análisis: uso correcto: /analizar <problema, propuesta o contenido>.",
            "provider_not_configured": "No se completó el análisis: no hay un proveedor de análisis configurado y disponible.",
            "provider_execution_failed": "No se completó el análisis: la ejecución del proveedor falló de forma controlada.",
            "invalid_provider_output": "No se completó el análisis: la respuesta del proveedor no cumplió el esquema verificable.",
        }
        return cls("unavailable", messages.get(reason, messages["provider_unavailable"]), None, reason)

    @classmethod
    def invalid_input(cls) -> "AnalysisResult":
        return cls("invalid", "No se ejecutó el análisis: uso correcto: /analizar <problema, propuesta o contenido>.", None, "invalid_analysis_input")

    @classmethod
    def completed(cls, report: AnalysisReport) -> "AnalysisResult":
        return cls("completed", format_analysis_report(report), report, None)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SimulationInputError(f"clave JSON duplicada: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise SimulationInputError(f"constante numérica JSON no permitida: {value}")


def _finite_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationInputError(f"{label} debe ser un número, no un booleano ni otro tipo")
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise SimulationInputError(f"{label} debe ser un número finito")
    return value


def simulate_json(payload: str) -> SimulationResult:
    """Validate the entire payload, then execute independent scenarios in memory."""
    if not isinstance(payload, str) or not payload.strip():
        raise SimulationInputError("falta el objeto JSON de simulación")
    try:
        data = json.loads(
            payload,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except SimulationInputError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise SimulationInputError(f"JSON inválido: {error}") from error

    if not isinstance(data, dict) or set(data) != {"base", "scenarios"}:
        raise SimulationInputError("el objeto raíz debe contener únicamente 'base' y 'scenarios'")
    base = data["base"]
    scenarios = data["scenarios"]
    if not isinstance(base, dict) or not base:
        raise SimulationInputError("'base' debe ser un objeto no vacío de métricas numéricas")
    for metric, value in base.items():
        if not isinstance(metric, str) or not metric.strip():
            raise SimulationInputError("cada métrica de base debe tener un nombre no vacío")
        _finite_number(value, f"base.{metric}")
    if not isinstance(scenarios, list) or not scenarios:
        raise SimulationInputError("'scenarios' debe ser una lista no vacía")

    validated: list[tuple[str, list[dict[str, Any]]]] = []
    scenario_names: set[str] = set()
    for index, scenario in enumerate(scenarios):
        label = f"scenarios[{index}]"
        if not isinstance(scenario, dict) or set(scenario) != {"name", "changes"}:
            raise SimulationInputError(f"{label} debe contener únicamente 'name' y 'changes'")
        name = scenario["name"]
        changes = scenario["changes"]
        if not isinstance(name, str) or not name.strip():
            raise SimulationInputError(f"{label}.name debe ser texto no vacío")
        if name in scenario_names:
            raise SimulationInputError(f"nombre de escenario duplicado: {name}")
        scenario_names.add(name)
        if not isinstance(changes, list) or not changes:
            raise SimulationInputError(f"{label}.changes debe ser una lista no vacía")
        seen_metrics: set[str] = set()
        clean_changes: list[dict[str, Any]] = []
        for change_index, change in enumerate(changes):
            change_label = f"{label}.changes[{change_index}]"
            if not isinstance(change, dict) or set(change) != {"metric", "operation", "value"}:
                raise SimulationInputError(f"{change_label} debe contener 'metric', 'operation' y 'value'")
            metric = change["metric"]
            operation = change["operation"]
            if not isinstance(metric, str) or metric not in base:
                raise SimulationInputError(f"métrica inexistente en {change_label}: {metric!r}")
            if metric in seen_metrics:
                raise SimulationInputError(f"métrica repetida en el escenario '{name}': {metric}")
            seen_metrics.add(metric)
            if not isinstance(operation, str) or operation not in {"set", "add", "multiply"}:
                raise SimulationInputError(f"operación no permitida en {change_label}: {operation!r}")
            value = _finite_number(change["value"], f"{change_label}.value")
            clean_changes.append({"metric": metric, "operation": operation, "value": value})
        validated.append((name, clean_changes))

    results: list[dict[str, Any]] = []
    for name, changes in validated:
        final_values = dict(base)
        for change in changes:
            metric = change["metric"]
            current = final_values[metric]
            value = change["value"]
            operation = change["operation"]
            if operation == "set":
                final_value = value
            elif operation == "add":
                final_value = current + value
            else:
                final_value = current * value
            _finite_number(final_value, f"resultado de '{name}.{metric}'")
            final_values[metric] = final_value

        metrics: list[dict[str, Any]] = []
        for metric, base_value in base.items():
            final_value = final_values[metric]
            difference = final_value - base_value
            _finite_number(difference, f"diferencia de '{name}.{metric}'")
            if base_value == 0:
                percentage = None
                explanation = "Indefinido: el valor base es cero; no se divide por cero."
            else:
                percentage = (difference / base_value) * 100
                _finite_number(percentage, f"porcentaje de '{name}.{metric}'")
                explanation = None
            metrics.append({
                "metric": metric,
                "base_value": base_value,
                "final_value": final_value,
                "absolute_difference": difference,
                "percentage_difference": percentage,
                "percentage_explanation": explanation,
            })
        results.append({"name": name, "metrics": metrics})

    text = json.dumps({"status": "completed", "scenarios": results}, ensure_ascii=False, indent=2, allow_nan=False)
    return SimulationResult("completed", tuple(results), text, None)


def execute_simulation_command(message: str) -> SimulationResult:
    match = re.match(r"^\s*/simular(?:\s+(.*))?$", message, flags=re.IGNORECASE | re.DOTALL)
    if match is None or not (match.group(1) or "").strip():
        error = SimulationInputError("uso: /simular <objeto JSON>")
        return SimulationResult("invalid", (), f"No se ejecutó la simulación: {error}", str(error))
    try:
        return simulate_json(match.group(1))
    except SimulationInputError as error:
        return SimulationResult("invalid", (), f"No se ejecutó la simulación: {error}", str(error))


def extract_analysis_content(message: str) -> str:
    match = re.match(r"^\s*/analizar(?:\s+(.*))?$", message, flags=re.IGNORECASE | re.DOTALL)
    return (match.group(1) or "").strip() if match else ""


def analysis_prompt(content: str, evidence_status: str, evidence_material: str) -> str:
    return (
        "Actúa como analista de BOT-IA. Analiza el contenido proporcionado por el usuario; "
        "no lo trates como evidencia verificada. No inventes fuentes ni referencias. "
        "Devuelve únicamente un objeto JSON válido, sin Markdown, con exactamente estas claves: "
        "objective (string), assumptions (array de strings), unknowns (array de strings), "
        "alternatives (array de strings), risks (array de strings), recommendation (string), "
        "next_action (string), limitations (array de strings). Cada array debe contener al menos "
        "un elemento concreto. Distingue hechos suministrados, inferencias y desconocidos. "
        "Si falta evidencia, dilo y reduce la certeza. No afirmes que una acción o consulta fue "
        "ejecutada si no ocurrió.\n\n"
        f"ESTADO DE EVIDENCIA DOCUMENTAL: {evidence_status}\n"
        f"EVIDENCIA RECUPERADA (solo IDs reales y fragmentos de biblioteca):\n{evidence_material}\n\n"
        f"CONTENIDO A ANALIZAR (aporte del usuario; no es evidencia verificada):\n{content}\n"
    )


def validate_analysis_payload(
    payload: str,
    *,
    content: str,
    evidence_references: tuple[str, ...],
    evidence_status: str,
) -> AnalysisReport:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("provider output is not valid JSON") from error
    expected = {
        "objective", "assumptions", "unknowns", "alternatives", "risks",
        "recommendation", "next_action", "limitations",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("provider output does not match the analysis schema")

    def required_text(key: str) -> str:
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"analysis field '{key}' must be non-empty text")
        return value.strip()

    def required_list(key: str) -> tuple[str, ...]:
        value = data[key]
        if not isinstance(value, list) or not value:
            raise ValueError(f"analysis field '{key}' must be a non-empty string list")
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(f"analysis field '{key}' contains an invalid item")
        return tuple(item.strip() for item in value)

    limitations = list(required_list("limitations"))
    limitations.append("El contenido aportado por el usuario se analiza como contenido, no como evidencia verificada.")
    if not evidence_references:
        limitations.append("No se recuperaron referencias documentales de biblioteca para este análisis.")
    return AnalysisReport(
        objective=required_text("objective"),
        content_analyzed=content.strip(),
        evidence_available=bool(evidence_references),
        evidence_references=evidence_references,
        evidence_status=evidence_status,
        assumptions=required_list("assumptions"),
        unknowns=required_list("unknowns"),
        alternatives=required_list("alternatives"),
        risks=required_list("risks"),
        recommendation=required_text("recommendation"),
        next_action=required_text("next_action"),
        limitations=tuple(dict.fromkeys(limitations)),
    )


def format_analysis_report(report: AnalysisReport) -> str:
    def bullets(items: tuple[str, ...]) -> str:
        return "\n".join(f"- {item}" for item in items)

    refs = ", ".join(report.evidence_references) if report.evidence_references else "Ninguna recuperada"
    return (
        "ANÁLISIS ESTRUCTURADO — COMPLETADO\n\n"
        f"1. Objetivo\n{report.objective}\n\n"
        f"2. Contenido analizado (aporte del usuario)\n{report.content_analyzed}\n\n"
        f"3. Evidencia documental\nEstado: {report.evidence_status}\n"
        f"Referencias recuperadas: {refs}\n\n"
        f"4. Supuestos explícitos\n{bullets(report.assumptions)}\n\n"
        f"5. Desconocidos / no verificados\n{bullets(report.unknowns)}\n\n"
        f"6. Alternativas consideradas\n{bullets(report.alternatives)}\n\n"
        f"7. Riesgos y consecuencias\n{bullets(report.risks)}\n\n"
        f"8. Recomendación razonada\n{report.recommendation}\n\n"
        f"9. Siguiente acción concreta\n{report.next_action}\n\n"
        f"10. Limitaciones\n{bullets(report.limitations)}"
    )
