import duckdb
import networkx as nx

DB_PATH = "data/sepsis_atlas.duckdb"


def build_graph() -> nx.Graph:
    """
    Build a NetworkX graph from the evidence database.

    Nodes: papers, predictors, outcomes
    Edges: paper → predictor (reported), paper → outcome (reported)
    """
    conn = duckdb.connect(DB_PATH)
    rows = conn.execute("""
        SELECT paper_id, study_label, predictor, outcome
        FROM evidence
        WHERE not_reported = FALSE
    """).fetchall()
    conn.close()

    G = nx.Graph()

    for paper_id, study_label, predictor, outcome in rows:
        paper_node = f"paper:{paper_id}"
        predictor_node = f"predictor:{predictor.lower().strip()}" if predictor else None
        outcome_node = f"outcome:{outcome.lower().strip()}" if outcome else None

        if not G.has_node(paper_node):
            G.add_node(paper_node, type="paper", label=study_label)
        if predictor_node and not G.has_node(predictor_node):
            G.add_node(predictor_node, type="predictor", label=predictor)
        if outcome_node and not G.has_node(outcome_node):
            G.add_node(outcome_node, type="outcome", label=outcome)

        if predictor_node:
            G.add_edge(paper_node, predictor_node)
        if outcome_node:
            G.add_edge(paper_node, outcome_node)

    return G


def find_papers_with_both(predictor: str, other_predictor: str) -> list[str]:
    """
    Multi-hop query: find papers that reported BOTH predictor A and predictor B.
    Returns list of study labels.
    """
    G = build_graph()
    p1 = f"predictor:{predictor.lower().strip()}"
    p2 = f"predictor:{other_predictor.lower().strip()}"

    if p1 not in G or p2 not in G:
        return []

    papers_with_p1 = {n for n in G.neighbors(p1) if G.nodes[n].get("type") == "paper"}
    papers_with_p2 = {n for n in G.neighbors(p2) if G.nodes[n].get("type") == "paper"}

    both = papers_with_p1 & papers_with_p2
    return [G.nodes[p].get("label", p) for p in both]


def find_co_reported_predictors(predictor: str) -> list[str]:
    """
    Find all other predictors that appeared in the same studies as the given predictor.
    """
    G = build_graph()
    p_node = f"predictor:{predictor.lower().strip()}"

    if p_node not in G:
        return []

    co_predictors = set()
    for paper in G.neighbors(p_node):
        if G.nodes[paper].get("type") == "paper":
            for neighbor in G.neighbors(paper):
                if G.nodes[neighbor].get("type") == "predictor" and neighbor != p_node:
                    co_predictors.add(G.nodes[neighbor].get("label", neighbor))

    return sorted(co_predictors)
