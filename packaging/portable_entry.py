"""Entry point used by portable release builds."""
import os

os.environ["AWC_PORTABLE"] = "1"

from main import main


if __name__ == "__main__":
    main()
