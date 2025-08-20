import os
import yaml
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_rules() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'rules.yaml')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            logger.info("Loaded rules.yaml (%s)", path)
            return data
    except Exception as e:
        logger.warning("Failed to load rules.yaml: %s", e)
        return {}


@lru_cache(maxsize=1)
def load_portion_rules() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'portion_rules.yaml')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            logger.info("Loaded portion_rules.yaml (%s)", path)
            return data
    except Exception as e:
        logger.warning("Failed to load portion_rules.yaml: %s", e)
        return {}


