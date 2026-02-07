"""Entry point for superpowers-dashboard."""
import argparse
from superpowers_dashboard.app import SuperpowersDashboard


def main():
    parser = argparse.ArgumentParser(description="Superpowers Dashboard")
    parser.add_argument("--project-dir", default=None, help="Project directory to monitor (defaults to CWD)")
    args = parser.parse_args()
    app = SuperpowersDashboard(project_dir=args.project_dir)
    app.run()


if __name__ == "__main__":
    main()
