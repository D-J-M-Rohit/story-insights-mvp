import argparse
import json

from app.retrieval import build_faiss_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="default")
    parser.add_argument("--scenario-pack", default=None)
    args = parser.parse_args()
    filters = {"scenario_pack_id": args.scenario_pack, "active": True} if args.scenario_pack else {"active": True}
    result = build_faiss_index(index_name=args.index, filters=filters)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
