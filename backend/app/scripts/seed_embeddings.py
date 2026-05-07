import argparse
import json

from app.embeddings import seed_embeddings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario-pack", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = seed_embeddings(scenario_pack_id=args.scenario_pack, force=args.force)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
