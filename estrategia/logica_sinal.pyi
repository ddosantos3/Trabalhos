# backend/estrategia/logica_sinal.pyi
from typing import Any, Dict, Optional

class Estrategia:
    # parâmetros esperados (dê match com sua implementação real)
    params: Dict[str, int]
    maior_periodo: int

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def processar_e_salvar_indicadores(self, df_klines: Any, par_ativo: str) -> Optional[Dict[str, Any]]: ...
    # outras funções possíveis usadas pelo projeto
    def sinal_de_compra(self, dados: Dict[str, Any]) -> bool: ...
    def sinal_de_venda(self, dados: Dict[str, Any]) -> bool: ...
