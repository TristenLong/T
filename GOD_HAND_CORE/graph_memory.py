import logging
import os

from neo4j import GraphDatabase

logger = logging.getLogger("GRAPH_MEMORY")
logger.setLevel(logging.INFO)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = None

def init_driver():
    global driver
    if driver is not None:
        return True
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        logger.info("Connected to Neo4j successfully.")
        return True
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {e}. Falling back to SQLite/Chroma.")
        driver = None
        return False

def save_memory(role, content):
    if not init_driver(): return False
    if driver is None: return False
    
    with driver.session() as session:
        query = """
        CREATE (m:Memory {role: $role, content: $content, timestamp: timestamp()})
        RETURN m
        """
        session.run(query, role=role, content=content)
    return True

def load_memories(limit=10):
    if not init_driver(): return None
    if driver is None: return None
    
    with driver.session() as session:
        query = """
        MATCH (m:Memory)
        RETURN m.role AS role, m.content AS content
        ORDER BY m.timestamp DESC LIMIT $limit
        """
        result = session.run(query, limit=limit)
        
        history = []
        for record in reversed(list(result)):
            role = 'user' if record['role'] == 'user' else 'model'
            history.append({'role': role, 'parts': [{'text': record['content']}]})
        return history

def semantic_search(query_text, top_k=3):
    if not init_driver(): return None
    if driver is None: return None
    
    with driver.session() as session:
        words = query_text.split()
        if not words: return ""
        # Simple keyword fallback matching in the graph
        condition = " OR ".join([f"m.content CONTAINS '{w}'" for w in words if len(w) > 4])
        if not condition:
            condition = f"m.content CONTAINS '{words[0]}'"
            
        cypher = f"""
        MATCH (m:Memory)
        WHERE {condition}
        RETURN m.content AS content
        LIMIT $limit
        """
        try:
            result = session.run(cypher, limit=top_k)
            docs = [record["content"] for record in result]
            if docs:
                return "RECALLED PAST CONTEXT (GRAPH): " + " | ".join(docs)
            return ""
        except Exception as e:
            logger.error(f"Graph Search Error: {e}")
            return None

def close():
    if driver:
        driver.close()
