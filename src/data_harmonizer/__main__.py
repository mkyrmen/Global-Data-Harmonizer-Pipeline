"""Enable ``python -m data_harmonizer`` to run the pipeline."""
import sys

from data_harmonizer.pipeline.runner import main

if __name__ == "__main__":
    sys.exit(main())