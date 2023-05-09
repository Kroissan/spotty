import io
import sys
import time

import requests.exceptions


def catch_stdout(func) -> str:
    for i in range(3):
        try:
            output_catch = io.StringIO()
            sys.stdout = output_catch
            func()
            sys.stdout = sys.__stdout__

            # get the output as a string
            return output_catch.getvalue()
        except requests.exceptions.HTTPError:
            time.sleep(15)