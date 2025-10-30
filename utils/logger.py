# /backend/utils/logger.py

import sys
from loguru import logger

# Remove o handler padrão para poder configurar do zero
logger.remove()

# Configuração do formato do log
# Adiciona um handler para exibir logs no console com cores e formato claro
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True
)

# Adiciona um handler para salvar logs em um arquivo
# 'rotation' cria um novo arquivo quando o atual atinge 10 MB
# 'retention' mantém os últimos 5 arquivos de log
logger.add(
    "logs/app_log_{time}.log",
    level="DEBUG",
    rotation="10 MB",
    retention="5 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    encoding="utf-8"
)

# Exporta a instância configurada para ser usada em outros módulos
log = logger
