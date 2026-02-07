"""Entry point for superpowers-dashboard."""
from superpowers_dashboard.app import SuperpowersDashboard


def main():
    app = SuperpowersDashboard()
    app.run()


if __name__ == "__main__":
    main()
