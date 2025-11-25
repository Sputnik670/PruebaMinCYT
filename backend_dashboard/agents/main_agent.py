from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool

from core.config import settings
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario

# 1. Configuración del Modelo
llm = ChatOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=settings.MODEL_NAME,
    temperature=0,
)

# 2. Definición del "Cerebro" (System Prompt Personalizado)
# Aquí es donde le damos la identidad para que sepa qué hacer.
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres el Asistente Inteligente del MinCYT (Ministerio de Ciencia y Tecnología). "
            "Tu misión es ayudar a los usuarios consultando la información disponible. "
            "\n\n"
            "TIENES ACCESO A DOS HERRAMIENTAS PODEROSAS:\n"
            "1. 'consultar_calendario': ÚSALA SIEMPRE que te pregunten por eventos, fechas, reuniones o agenda del ministerio.\n"
            "2. 'tavily_search_results_json': Úsala solo para buscar información pública en internet (noticias, datos generales).\n"
            "\n\n"
            "REGLAS:\n"
            "- Si te preguntan 'qué hay en febrero', PRIMERO consulta el calendario.\n"
            "- Si no encuentras nada en el calendario, dilo claramente antes de inventar cosas genéricas.\n"
            "- Sé amable, profesional y conciso."
        ),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# 3. Herramientas
search_tool = get_search_tool()
tools = [search_tool, consultar_calendario]

# 4. Crear el Agente con el nuevo Prompt
agent_runnable = create_openai_functions_agent(llm, tools, prompt)

# 5. Ejecutor (Mantiene el manejo de errores que nos salvó antes)
agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True 
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 Pregunta: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error crítico: {str(e)}")
        return "Estoy teniendo problemas de conexión con mis herramientas. Por favor verifica mi configuración."