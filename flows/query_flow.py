import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefect import flow, task
from pipeline.query.router import route_query
from pipeline.query.expander import expand_query
from pipeline.query.sql_generator import query_to_dataframe
from pipeline.query.bm25_fallback import bm25_search


@task
def task_expand(query: str) -> str:
    return expand_query(query)


@task
def task_route(expanded_query: str) -> str:
    return route_query(expanded_query)


@task
def task_sql_query(expanded_query: str):
    return query_to_dataframe(expanded_query)


@task
def task_bm25_query(expanded_query: str) -> list:
    return bm25_search(expanded_query)


@flow(name="query-pipeline", log_prints=True)
def run_query(natural_language_query: str):
    """Run a full query through the pipeline and return results."""
    expanded = task_expand(natural_language_query)
    print(f"Expanded query: {expanded}")

    route = task_route(expanded)
    print(f"Route: {route}")

    if route in ("sql", "graph"):
        df, sql = task_sql_query(expanded)
        print(f"Results: {len(df)} records")
        print(df[["study_label", "predictor", "outcome", "confidence"]].to_string())
        return df
    else:
        results = task_bm25_query(expanded)
        print(f"BM25 results: {len(results)} passages")
        for r in results:
            print(f"  [{r['study_label']}] score={r['score']:.2f}: {r['text'][:100]}...")
        return results


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What predicts 28-day mortality?"
    run_query(query)
    