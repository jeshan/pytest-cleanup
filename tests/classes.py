import threading


class Hi:
    pass


class Inner1:
    class Inner:
        pass

    def go(self):
        return Inner1.Inner


class Inner2:
    class Inner:
        def __init__(self, value):
            self.value = value

        def go(self):
            return 1

        def __eq__(self, other):
            return isinstance(other, self.__class__) and self.value == other.value

    def go(self):
        return Inner2.Inner(1)


class Inner3:
    class Inner:
        def go(self):
            return 1

    def go(self):
        return Inner3.Inner().go()


class Inner4:
    class Inner:
        def higher_order(self, fn):
            return fn

    def pass_inner(self, fn):
        inner = Inner4.Inner()
        return inner.higher_order(fn)


class Inner5:
    class Inner:
        def higher_order(self, fn):
            return fn

    def pass_inner(self, clazz):
        return Inner5.Inner

    def pass_back(self, clazz):
        return clazz


class Hey:
    def __init__(self, value):
        super(Hey, self).__init__()
        from random import random

        self.value = value * random()

    def go_instance(self):
        print('in go_instance')
        self.go_instance2()
        return self.value * 3

    def go_instance2(self):
        print('in go_instance2')
        return self.value * 33

    def call_all_method(self):
        """calls different class methods to confirm calling all supported method types are properly recorded"""
        self.go_instance()
        Hey.go_static()
        Hey.go_class()

    @staticmethod
    def call_all_static_method():
        """calls different class methods to confirm calling all supported method types are properly recorded"""
        Hey(3).go_instance()
        Hey.go_static()
        Hey.go_class()

    @classmethod
    def call_all_class_method(cls):
        """calls different class methods to confirm calling all supported method types are properly recorded"""
        Hey(4).go_instance()
        Hey.go_static()
        cls.go_static()
        cls.go_class()
        Hey.go_class()

    @staticmethod
    def go_static():
        print('in static')
        Hey.go_static2()
        return 'static'

    @staticmethod
    def go_static2():
        print('in static2')
        return 'static2'

    @classmethod
    def go_class(cls):
        print('in class')
        cls.go_class2()
        return 123

    @classmethod
    def go_class2(cls):
        print('in class2')
        return 321


class HeyThread(threading.Thread):
    def __init__(self, value):
        super(HeyThread, self).__init__()

    def run(self):
        print('running')
