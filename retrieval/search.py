"""Run one development search from the command line."""
import argparse
import json
from .service import SearchService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    args = parser.parse_args()
    service = SearchService()
    service.holdout.require_development(args.question)
    service.load_model()
    result = service.search(args.question)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
