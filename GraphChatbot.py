import os 
from dotenv import load_dotenv
load_dotenv()

os.environ["GROQ_API_KEY"] = os.getenv("groq_api_key")
os.environ["HF__TOKEN"] = os.getenv("HF__TOKEN")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGSMITH_API_KEY"] = os.getenv("langsmith_api_key")

from langchain_groq import ChatGroq
llm =ChatGroq(model="llama-3.1-8b-instant",api_key=os.getenv("GROQ_API_KEY"))

#Chatbot using langgraph 
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph,START,END   #Stategraph will change node to node
from langgraph.graph.message import add_messages   #State of agent getting changes with mess from user.

class State(TypedDict):
    #Messages have the type "list. the 'add_message" function
    # in the annotations defines how this state key should be updated

    messages: Annotated[list,add_messages]
graph_builder=StateGraph(State)
graph_builder

def chatbot(state:State):
    return {"messages":llm.invoke(state["messages"])}

graph_builder.add_node("chatbot",chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot",END)


#Compile the graph
graph = graph_builder.compile()

#Display the graph
from IPython.display import Image,display
try:
    display(Image(graph.get_graph().draw_mermaid_png()))
except Exception as e:
    pass

while True:
    user_input = input("User:")
    if user_input.lower() in ["quit","exit","bye"]:
        print("Goodbye!")
        break
    for event in graph.stream({"messages":[user_input]}):
        print(event.values())
        print("--------------------------------")
        for value in event.values():
            print(value['messages'])
            print("Assistant:",value['messages'].content)

             