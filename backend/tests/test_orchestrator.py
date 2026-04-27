from unittest.mock import MagicMock, patch

from backend.services.orchestrator import orchestrate_user_request


@patch("backend.services.orchestrator.OpenAI")
def test_orchestrate_user_request_chat(mock_openai):
    # Mock LLM response for chat
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"intent": "chat", "chat_response": "Hello, how can I help you?"}'
    )
    mock_client.chat.completions.create.return_value.choices = [mock_choice]
    mock_openai.return_value = mock_client

    result = orchestrate_user_request("Hi there", session_id="test")

    assert result["type"] == "chat"
    assert "response" in result
