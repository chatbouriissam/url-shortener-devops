"""One-shot GitHub setup for the DevOps project.

Run it from INSIDE your cloned repo.

  python setup_repo.py --dry-run                  # preview only
  python setup_repo.py                            # labels + 16 issues
  python setup_repo.py --project 1 --protect      # + add to board #1 + protect main

Safe to re-run: issues whose title already exists are skipped.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys

LABELS = {
    "backend": "0E8A16", "docker": "0DB7ED", "ci-cd": "1D76DB",
    "observability": "FBCA04", "security": "D93F0B",
    "kubernetes": "326CE5", "docs": "5319E7",
}

# (title, label, goal, depends_on [positions in this list, 1-based], done_when)
ISSUES = [
    ("Repo setup", "docs", "Foundation of the project.", [],
     ["README skeleton", ".gitignore", "Branch protection on main", "Project board"]),
    ("Backend: FastAPI endpoints", "backend", "A small URL shortener API.", [1],
     ["POST /shorten with URL validation", "GET /{code} redirect or 404",
      "GET /stats/{code}", "GET /health", "Whole app under 150 lines"]),
    ("Unit tests", "backend", "Prove the API works.", [2],
     ["pytest + TestClient", "Tests: shorten, redirect, 404, stats", "All green locally"]),
    ("Dockerfile", "docker", "Containerize the API.", [2],
     ["Slim base image", "Non-root user", ".dockerignore", "Runs on port 8000"]),
    ("Docker compose", "docker", "Run the stack with one command.", [4],
     ["API service", "Prometheus service", "Grafana service", "docker compose up works"]),
    ("CI pipeline", "ci-cd", "Automatic build and test on every PR.", [3, 4],
     ["Workflow on push and PR", "Install, lint, pytest", "Docker build",
      "Set as required check on main"]),
    ("Metrics", "observability", "Expose Prometheus metrics.", [2, 5],
     ["/metrics endpoint", "Request count", "Latency histogram", "Grafana dashboard"]),
    ("Structured logs", "observability", "JSON logs for requests and errors.", [2],
     ["JSON format", "Method, path, status, duration per request", "Errors logged",
      "Sample saved as evidence"]),
    ("Tracing", "observability", "Basic request tracing.", [2, 5],
     ["OpenTelemetry setup", "One trace per request", "Trace ID in logs",
      "Trace visible in Jaeger"]),
    ("SAST", "security", "Static scan of code and image.", [6],
     ["Bandit or Semgrep in CI", "Trivy image scan", "Reports kept as artifacts",
      "Findings triaged"]),
    ("Publish Docker image", "ci-cd", "Push the image to Docker Hub from CI.", [6],
     ["Docker Hub secrets in GitHub", "Push on merge to main", "Tags: commit SHA and latest"]),
    ("Kubernetes manifests", "kubernetes", "Describe the deployment.", [4],
     ["Deployment", "Service", "Liveness and readiness probes on /health", "Resource limits"]),
    ("Local Kubernetes deploy", "kubernetes", "Run it on kind or minikube.", [11, 12],
     ["Cluster created", "Pods running", "API reachable",
      "Screenshot of kubectl get pods,svc"]),
    ("DAST", "security", "Runtime scan of the deployed API.", [13],
     ["OWASP ZAP baseline scan", "Report saved", "Findings triaged"]),
    ("CD: automatic deployment", "ci-cd", "Pipeline deploys after tests and scans.", [11, 13],
     ["Workflow creates a kind cluster", "Applies manifests", "Smoke test on /health",
      "Run ZAP in the same job"]),
    ("Docs, report and slides", "docs", "Final deliverables.", [1],
     ["README: setup, local run, Docker, API examples", "1-2 page report",
      "10 min slides", "Evidence screenshots collected"]),
]


def gh(*args, stdin=None):
    """Run a gh command; stop with a readable message if it fails."""
    res = subprocess.run(["gh", *args], input=stdin, text=True, encoding="utf-8",
                         capture_output=True)
    if res.returncode != 0:
        sys.exit(f"\nERROR running: gh {' '.join(args[:4])} ...\n{res.stderr.strip()}")
    return res.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print actions, change nothing")
    ap.add_argument("--project", type=int, help="project board number to add issues to")
    ap.add_argument("--protect", action="store_true", help="enable branch protection on main")
    args = ap.parse_args()

    if args.dry_run:
        repo = "<your-user>/<your-repo>"
    else:
        if not shutil.which("gh"):
            sys.exit("GitHub CLI not found. Install it (winget install --id GitHub.cli), "
                     "then CLOSE and REOPEN your terminal.")
        gh("auth", "status")
        repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    print(f"Repository: {repo}\n")

    for name, color in LABELS.items():
        print(f"label  {name}")
        if not args.dry_run:
            gh("label", "create", name, "--color", color, "--force")

    existing = {}
    if not args.dry_run:
        for it in json.loads(gh("issue", "list", "--state", "all",
                                "--json", "number,title", "--limit", "500")):
            existing[it["title"]] = it["number"]

    number_of = {}  # position in ISSUES (1-based) -> real GitHub issue number
    for pos, (title, label, goal, deps, checks) in enumerate(ISSUES, start=1):
        if title in existing:
            number_of[pos] = existing[title]
            print(f"skip   #{existing[title]} {title} (already exists)")
            continue
        body = f"## Goal\n{goal}\n\n"
        if deps:
            body += "**Depends on:** " + ", ".join(f"#{number_of[d]}" for d in deps) + "\n\n"
        body += "## Done when\n" + "\n".join(f"- [ ] {c}" for c in checks)
        if args.dry_run:
            number_of[pos] = pos
            print(f"create #{pos} [{label}] {title}")
            continue
        out = gh("issue", "create", "--title", title, "--body", body, "--label", label)
        number_of[pos] = int(re.search(r"/issues/(\d+)", out).group(1))
        print(f"create #{number_of[pos]} [{label}] {title}")

    if args.project:
        owner = repo.split("/")[0]
        for pos, num in number_of.items():
            print(f"board  #{num} -> project {args.project}")
            if not args.dry_run:
                gh("project", "item-add", str(args.project), "--owner", owner,
                   "--url", f"https://github.com/{repo}/issues/{num}")

    if args.protect:
        print("protect main: require pull request before merging")
        if not args.dry_run:
            rules = {
                "required_status_checks": None,
                "enforce_admins": False,
                "required_pull_request_reviews": {"required_approving_review_count": 0},
                "restrictions": None,
            }
            gh("api", "-X", "PUT", f"repos/{repo}/branches/main/protection",
               "--input", "-", stdin=json.dumps(rules))

    print("\nDone." if not args.dry_run else "\nDry run finished, nothing was changed.")


if __name__ == "__main__":
    main()
