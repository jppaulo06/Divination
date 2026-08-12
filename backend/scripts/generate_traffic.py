#!/usr/bin/env python3
"""Drive synthetic traffic through the running API to populate monitoring.

Each entry in traffic_questions.json becomes one chat; multi-turn entries
send their turns in order so thread-scoped detectors have history to work
with. Answers are optionally rated to exercise the feedback path.

    python scripts/generate_traffic.py --base-url http://localhost:8000

Uses only the stdlib, so it runs without installing anything.
"""

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_QUESTIONS = Path(__file__).with_name("traffic_questions.json")


def post(base_url: str, path: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def create_chat(base_url: str, timeout: float) -> str:
    return post(base_url, "/v1/chats", {}, timeout)["chatId"]


def ask(base_url: str, chat_id: str, question: str, timeout: float) -> dict:
    return post(
        base_url,
        "/v1/answer",
        {"userQuestion": question, "chatId": chat_id},
        timeout,
    )


def rate(
    base_url: str,
    interaction_id: str,
    rating: int,
    comment: str,
    timeout: float,
) -> None:
    post(
        base_url,
        "/v1/feedback",
        {
            "interactionId": interaction_id,
            "rating": rating,
            "comment": comment,
        },
        timeout,
    )


def run(args) -> int:
    threads = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    if args.limit:
        threads = threads[: args.limit]

    rng = random.Random(args.seed)
    asked = 0
    rated = 0
    failed = 0

    for thread in threads:
        try:
            chat_id = create_chat(args.base_url, args.timeout)
        except (urllib.error.URLError, urllib.error.HTTPError) as failure:
            print(f"! could not create chat: {failure}", file=sys.stderr)
            return 1

        for question in thread["turns"]:
            try:
                answer = ask(args.base_url, chat_id, question, args.timeout)
            except (urllib.error.URLError, urllib.error.HTTPError) as failure:
                failed += 1
                print(
                    f"! {thread['name']}: {failure}",
                    file=sys.stderr,
                )
                continue

            asked += 1
            interaction_id = answer.get("interactionId")
            print(f"  {thread['name']}: {question[:60]}")

            if (
                interaction_id
                and args.feedback_rate > 0
                and rng.random() < args.feedback_rate
            ):
                rating = -1 if rng.random() < args.negative_share else 1
                try:
                    rate(
                        args.base_url,
                        interaction_id,
                        rating,
                        "simulated rating from generate_traffic.py",
                        args.timeout,
                    )
                    rated += 1
                except (urllib.error.URLError, urllib.error.HTTPError) as e:
                    print(f"! rating failed: {e}", file=sys.stderr)

    print(
        f"\nasked={asked} rated={rated} failed={failed}\n"
        f"inspect with: curl {args.base_url}/v1/monitoring/summary"
    )
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument(
        "--limit", type=int, default=0, help="only run the first N threads"
    )
    parser.add_argument(
        "--feedback-rate",
        type=float,
        default=0.25,
        help="fraction of answers that receive a simulated rating",
    )
    parser.add_argument(
        "--negative-share",
        type=float,
        default=0.6,
        help="fraction of simulated ratings that are negative",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=1234)
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
