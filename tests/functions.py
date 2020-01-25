from random import random


from pytest_cleanup import Recorder


def sub():
    print('in sub')

    def inner():
        print('in inner')

        def inner2():
            print('in inner2')

        inner2()

    inner()

    from datetime import datetime

    return datetime(1970, 1, 1)


def return1():
    return 1


def go(a, b):
    print('in go')

    # @profile
    def inner():
        print('in inner2')

    sub()
    inner()
    return random()


def higher_order(fn):
    def inner():
        return fn()

    return inner


def higher_order2():
    from random import random

    def inner():
        return random()

    return inner


def generator1(count):
    for i in range(count):
        yield i


def higher_order3():

    return return1


async def print_header(c, a=None, b=None):
    print('some async message')
    return 1


async def go_async():
    result = higher_order(higher_order2)
    higher_order3()
    generator1(2)
    generator1(3)
    generator1(2)
    result()()
    higher_order2()
    higher_order3()
    return1()
    return1()
    await print_header('hey', b='hi')
    # boto3.setup_default_session()
    # print_clients()


def start():
    go(1, 2)
    sub()
    another.go(2, 3)


#
# if __name__ == '__main__':
#     with Recorder():
#         start()
#         # go(1, 2) #
#     # Recorder().exit()
