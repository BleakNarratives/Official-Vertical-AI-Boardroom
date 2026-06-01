#!/usr/bin/env python3
"""
VERTICAL AI -- State Manager
Neo4j session lineage. Non-fatal if unavailable.
"""

import os
import json
from datetime import datetime

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "password")


def get_driver():
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        driver.verify_connectivity()
        return driver
    except Exception:
        return None


def save_run(session_id, input_context, boardroom, tracks, arena):
    driver = get_driver()
    if not driver:
        print("  Neo4j unavailable -- run not persisted (continuing)")
        return False
    try:
        with driver.session() as s:
            s.run("MERGE (n:VerticalAISession {id:$id}) SET n.timestamp=$ts, n.label=$label, n.verdict=$verdict",
                id=session_id, ts=datetime.now().isoformat(),
                label=input_context.get("label",""), verdict=boardroom.get("synthesis",{}).get("verdict",""))
            champion = arena.get("champion",{})
            if champion:
                s.run("""MERGE (c:Champion {session_id:$sid})
                    SET c.name=$name, c.thesis=$thesis, c.first_action=$action, c.mutation=$mutation, c.target_outcome=$outcome
                    WITH c MATCH (s:VerticalAISession {id:$sid}) MERGE (s)-[:CHAMPION]->(c)""",
                    sid=session_id, name=champion.get("name",""), thesis=champion.get("thesis",""),
                    action=champion.get("first_action",""), mutation=champion.get("mutation",""),
                    outcome=champion.get("target_outcome",""))
        driver.close()
        return True
    except Exception as e:
        print(f"  Neo4j write failed: {e}")
        return False


def load_session(session_id):
    driver = get_driver()
    if not driver:
        return None
    try:
        with driver.session() as s:
            result = s.run("""MATCH (s:VerticalAISession {id:$id})-[:CHAMPION]->(c)
                RETURN s.label as label, s.verdict as verdict, c.name as champion_name,
                c.thesis as thesis, c.first_action as first_action, c.mutation as mutation,
                c.target_outcome as target_outcome""", id=session_id)
            record = result.single()
            if record:
                return dict(record)
        driver.close()
    except Exception as e:
        print(f"  Neo4j read failed: {e}")
    return None


def list_sessions(limit=10):
    driver = get_driver()
    if not driver:
        return []
    try:
        with driver.session() as s:
            result = s.run("""MATCH (s:VerticalAISession) OPTIONAL MATCH (s)-[:CHAMPION]->(c)
                RETURN s.id as id, s.timestamp as ts, s.label as label, s.verdict as verdict, c.name as champion
                ORDER BY s.timestamp DESC LIMIT $limit""", limit=limit)
            return [dict(r) for r in result]
    except Exception as e:
        print(f"  Neo4j list failed: {e}")
        return []
