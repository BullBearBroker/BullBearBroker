from types import MethodType

import pytest
import asyncio

from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture(autouse=True)
def configure_providers(monkeypatch):
    monkeypatch.setattr(ai_service_module.Config, 'HUGGINGFACE_API_KEY', 'test-token', raising=False)
    monkeypatch.setattr(ai_service_module.Config, 'HUGGINGFACE_MODEL', 'test/model', raising=False)
    monkeypatch.setattr(ai_service_module.Config, 'HUGGINGFACE_API_URL', 'https://example.com/models', raising=False)
    monkeypatch.setattr(ai_service_module.Config, 'OLLAMA_HOST', 'http://localhost:11434', raising=False)
    monkeypatch.setattr(ai_service_module.Config, 'OLLAMA_MODEL', 'test-ollama', raising=False)


@pytest.fixture
def service():
    instance = AIService()

    async def fake_market_context(self, _message):
        return {}

    instance.get_market_context = MethodType(fake_market_context, instance)
    return instance


@pytest.mark.anyio
async def test_process_message_retries_before_switch(service, monkeypatch):
    attempts = {'count': 0}

    async def mistral_success_third(self, message, context):
        attempts['count'] += 1
        if attempts['count'] < 3:
            raise RuntimeError('temporary failure')
        return 'respuesta mistral'

    hf_calls = {'count': 0}

    async def huggingface_provider(self, message, context):
        hf_calls['count'] += 1
        return 'respuesta huggingface'

    ollama_calls = {'count': 0}

    async def ollama_provider(self, message, context):
        ollama_calls['count'] += 1
        return 'respuesta ollama'

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(AIService, 'process_with_mistral', mistral_success_third)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_provider)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_provider)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('¿Cómo está el mercado?')

    assert result.text == 'respuesta mistral'  # [Codex] cambiado - ahora devolvemos payload
    assert result.provider == 'mistral'
    assert attempts['count'] == 3
    assert hf_calls['count'] == 0
    assert ollama_calls['count'] == 0
    assert sleep_calls == [1, 2]


@pytest.mark.anyio
async def test_process_message_falls_back_to_huggingface(service, monkeypatch):
    attempts = {'count': 0}

    async def mistral_failure(self, message, context):
        attempts['count'] += 1
        raise RuntimeError('mistral down')

    hf_calls = {'count': 0}

    async def huggingface_success(self, message, context):
        hf_calls['count'] += 1
        return 'respuesta huggingface'

    async def ollama_provider(self, message, context):
        raise AssertionError('Ollama no debería ser llamado')

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(AIService, 'process_with_mistral', mistral_failure)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_success)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_provider)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('Dame ideas de inversión')

    assert result.text == 'respuesta huggingface'  # [Codex] cambiado
    assert result.provider == 'huggingface'
    assert attempts['count'] == 3
    assert hf_calls['count'] == 1
    assert sleep_calls == [1, 2]


@pytest.mark.anyio
async def test_process_message_falls_back_to_ollama(service, monkeypatch):
    async def mistral_failure(self, message, context):
        raise RuntimeError('mistral down')

    hf_attempts = {'count': 0}

    async def huggingface_failure(self, message, context):
        hf_attempts['count'] += 1
        raise RuntimeError('huggingface down')

    ollama_calls = {'count': 0}

    async def ollama_success(self, message, context):
        ollama_calls['count'] += 1
        return 'respuesta ollama'

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(AIService, 'process_with_mistral', mistral_failure)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_failure)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_success)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('¿Qué opinas de BTC?')

    assert result.text == 'respuesta ollama'  # [Codex] cambiado
    assert result.provider == 'ollama'
    assert hf_attempts['count'] == 3
    assert ollama_calls['count'] == 1
    assert sleep_calls == [1, 2, 1, 2]


@pytest.mark.anyio
async def test_process_message_uses_local_fallback(service, monkeypatch):
    async def mistral_failure(self, message, context):
        raise RuntimeError('mistral down')

    async def huggingface_failure(self, message, context):
        raise RuntimeError('huggingface down')

    async def ollama_failure(self, message, context):
        raise RuntimeError('ollama down')

    async def local_response(self, message):
        return 'respuesta local'

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(AIService, 'process_with_mistral', mistral_failure)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_failure)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_failure)
    monkeypatch.setattr(AIService, 'generate_response', local_response)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('Necesito asesoría financiera')

    assert result.text == 'respuesta local'  # [Codex] cambiado
    assert result.provider == 'local'
    assert sleep_calls == [1, 2, 1, 2, 1, 2]


@pytest.mark.anyio
async def test_process_message_empty_prompt_uses_local_fallback(service, monkeypatch):
    async def mistral_failure(self, message, context):
        raise ValueError('mensaje vacío')

    async def huggingface_failure(self, message, context):
        raise ValueError('mensaje vacío')

    async def ollama_failure(self, message, context):
        raise ValueError('mensaje vacío')

    async def fake_sleep(delay):
        pass

    async def local_response(self, message):
        return 'respuesta predeterminada'

    monkeypatch.setattr(AIService, 'process_with_mistral', mistral_failure)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_failure)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_failure)
    monkeypatch.setattr(AIService, 'generate_response', local_response)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('   ')

    assert result.provider == 'local'
    assert result.text == 'respuesta predeterminada'


@pytest.mark.anyio
async def test_process_message_timeout_in_primary_provider(service, monkeypatch):
    attempts = {'count': 0}

    async def mistral_timeout(self, message, context):
        attempts['count'] += 1
        raise asyncio.TimeoutError('timeout')

    hf_calls = {'count': 0}

    async def huggingface_success(self, message, context):
        hf_calls['count'] += 1
        return 'respuesta alternativa'

    async def ollama_not_called(self, message, context):
        raise AssertionError('Ollama no debería ejecutarse en este escenario')

    async def fake_sleep(delay):
        pass

    monkeypatch.setattr(AIService, 'process_with_mistral', mistral_timeout)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_success)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_not_called)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('Analiza el mercado del oro')

    assert attempts['count'] == 3
    assert hf_calls['count'] == 1
    assert result.provider == 'huggingface'
    assert result.text == 'respuesta alternativa'


@pytest.mark.anyio
async def test_process_message_invalid_model_response(service, monkeypatch):
    async def fake_generate(message, context):
        return 'Lo siento, estoy teniendo dificultades para responder'

    hf_calls = {'count': 0}

    async def huggingface_success(self, message, context):
        hf_calls['count'] += 1
        return 'respuesta huggingface válida'

    async def ollama_not_called(self, message, context):
        raise AssertionError('Ollama no debería ser llamado')

    async def fake_sleep(delay):
        pass

    monkeypatch.setattr(ai_service_module.mistral_service, 'generate_financial_response', fake_generate)
    monkeypatch.setattr(AIService, '_call_huggingface', huggingface_success)
    monkeypatch.setattr(AIService, '_call_ollama', ollama_not_called)
    monkeypatch.setattr(ai_service_module.asyncio, 'sleep', fake_sleep)

    result = await service.process_message('Analiza BTC')

    assert hf_calls['count'] == 1
    assert result.provider == 'huggingface'
    assert result.text == 'respuesta huggingface válida'
