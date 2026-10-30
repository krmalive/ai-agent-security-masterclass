import os
import uuid
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from backend.config import Config
from backend.agent.lab_agent import create_chat_agent

app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
)
app.config.from_object(Config)

os.makedirs(Config.CHROMA_DB_PATH, exist_ok=True)


def _warmup_embedding_model() -> None:
    try:
        from backend.agent.embeddings import get_embedding_function

        get_embedding_function()
    except Exception as exc:
        print(f"Warning: embedding model warmup failed: {exc}")


_warmup_embedding_model()


@app.route('/')
def index():
    mode = Config.MODE
    return render_template('chat.html', mode=mode)


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        user_message = request.form.get('message', '').strip()
        session_id = request.form.get('session_id', '')
        context = request.form.get('context', '')

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        chat_history = []
        try:
            chat_history = json.loads(request.form.get('history', '[]'))
        except Exception:
            chat_history = []

        if not session_id:
            session_id = str(uuid.uuid4())

        chat_agent = create_chat_agent()
        result = chat_agent.chat(
            user_message=user_message,
            chat_history=chat_history,
            context=context,
            session_id=session_id
        )

        return jsonify({
            'session_id': session_id,
            'response': result.get('response', ''),
            'agent_triggered': result.get('agent_triggered', ''),
            'results': result.get('results', {})
        }), 200

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/agents', methods=['GET'])
def get_agents():
    try:
        agents_info = [{
            "name": "Policy Assistant",
            "description": "Customer service agent — stores facts, retrieves policies, processes refunds",
            "capabilities": [
                "add_to_memory — store facts, policies, preferences (HIGH RISK: poisoning surface)",
                "query_memory — search stored memory entries",
                "get_refund_policy — retrieve current refund policy (baseline + memory)",
                "query_order — lookup order status and details",
                "process_refund — evaluate and process refund requests (HIGH RISK: policy-dependent)"
            ]
        }]

        agents_info.append({
            "name": "Memory Validator",
            "description": "Runs when MODE=defense before add_to_memory (backend.agent.guardrails.MemoryValidator). Not used when MODE=attack.",
            "capabilities": [
                "validate_memory_write — LLM allow/deny gate (defense only)",
            ],
        })

        return jsonify({
            "agents": agents_info,
            "mode": Config.MODE
        }), 200
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/memory', methods=['GET'])
def get_memory():
    try:
        from backend.agent.seed import MemoryStore
        store = MemoryStore()
        entries = store.get_all_memory_entries()
        return jsonify({"entries": entries, "count": len(entries)}), 200
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/policies', methods=['GET'])
def get_policies():
    try:
        from backend.agent.seed import MemoryStore
        store = MemoryStore()
        policies = store.get_baseline_policies()
        return jsonify({"policies": policies}), 200
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/reset', methods=['POST'])
def reset_memory():
    """Clear all user memory entries — resets the lab between scenarios."""
    try:
        from backend.agent.seed import MemoryStore
        store = MemoryStore()
        result = store.clear_memory()
        return jsonify(result), 200
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
