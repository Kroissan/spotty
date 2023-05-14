import io
import sys
import time

import requests.exceptions


def catch_stdout(func) -> str:
    error = ValueError('Function returned no data.')
    for i in range(3):
        try:
            output_catch = io.StringIO()
            sys.stdout = output_catch
            func()
            sys.stdout = sys.__stdout__

            # get the output as a string
            return output_catch.getvalue()
        except requests.exceptions.HTTPError as e:
            error = e
            time.sleep(15)

    raise error
