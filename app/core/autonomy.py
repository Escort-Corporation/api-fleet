"""Travas do motorista autônomo (ver MOTORISTA_AUTONOMO.md na raiz).

O autônomo fica PREPARADO e DESLIGADO no MVP. Ligar (`AUTONOMOUS_DRIVERS_ENABLED=true`) só é
aceito com as condições que não são de código confirmadas — jurídico de transporte (Lei
11.442/2007, piso ANTT), seguro de carga e RC, processo de RNTRC/CIOT. Sem elas o serviço não
sobe. A condição de volume é checada em tempo de execução pelo api-matching
(`candidate_service.autonomous_offers_allowed`).

Cópia idêntica em api-matching, api-fleet e api-freight: repositórios independentes, sem pacote comum
(mesmo padrão de AppError e geo.py).
"""

from pydantic import BaseModel, Field, model_validator


class AutonomySettings(BaseModel):
    autonomous_drivers_enabled: bool = False
    # Advogado de transporte validou o modelo (contratante do transporte, Lei 11.442/2007,
    # piso mínimo de frete, risco trabalhista).
    autonomous_legal_review_done: bool = False
    # Seguro de carga e responsabilidade civil cobrindo o frete do autônomo.
    autonomous_cargo_insurance_active: bool = False
    # Emissão/checagem de RNTRC e CIOT para o frete avulso.
    autonomous_rntrc_ciot_ready: bool = False
    # Escolha real exige volume: abaixo disso, oferta para autônomo não é gerada.
    autonomous_min_weekly_offers: int = Field(default=50, gt=0)

    @model_validator(mode="after")
    def _legal_gates_before_enabling(self) -> "AutonomySettings":
        if self.autonomous_drivers_enabled:
            missing = [
                name
                for name, ok in (
                    ("AUTONOMOUS_LEGAL_REVIEW_DONE", self.autonomous_legal_review_done),
                    ("AUTONOMOUS_CARGO_INSURANCE_ACTIVE", self.autonomous_cargo_insurance_active),
                    ("AUTONOMOUS_RNTRC_CIOT_READY", self.autonomous_rntrc_ciot_ready),
                )
                if not ok
            ]
            if missing:
                raise ValueError(
                    "AUTONOMOUS_DRIVERS_ENABLED=true exige as condições do MOTORISTA_AUTONOMO.md: "
                    + ", ".join(missing)
                )
        return self
