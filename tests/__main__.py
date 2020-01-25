import select
import threading
from collections import deque

import asyncio


from pytest_cleanup import Recorder
from .functions import go_async
from .classes import Inner1, Inner2, Inner3, Inner4, Inner5, Hey


def main():
    def hey():
        print('hey')

    loop = asyncio.get_event_loop()
    with Recorder():
        loop.run_until_complete(go_async())
        # higher_order2()
        Inner1().go()
        Inner2().go()
        Inner3().go()
        Inner4().pass_inner(hey)
        Inner4().pass_inner(Inner3().go)
        Inner5().pass_inner(Inner3().Inner)
        Inner5().pass_back(Inner3().Inner)

        Hey(1).go_instance()
        Hey.go_class()
        Hey.go_static()
        hey = Hey(2)
        hey.call_all_method()
        Hey.call_all_class_method()
        Hey.call_all_static_method()

    loop.close()


if __name__ == '__main__':
    main()
