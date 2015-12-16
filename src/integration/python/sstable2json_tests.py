
import json
from common import *
from tempfile import NamedTemporaryFile

CREATE_USER_TABLE = """
    CREATE TABLE users (
        user_name varchar PRIMARY KEY,
        password varchar,
        gender varchar,
        state varchar,
        birth_year bigint
    );
"""

COMPOSITE_TABLE = """
    CREATE TABLE composites (
        key1 varchar,
        key2 varchar,
        ckey1 varchar,
        ckey2 varchar,
        value bigint,
        PRIMARY KEY((key1, key2), ckey1, ckey2)
    );
"""

class TestKeysOnly(IntegrationTest):
    def __init__(self, methodName='runTest'):
        TestCase.__init__(self, methodName)
        self.name = 'TestKeysOnly'

    def test_single_key(self):
        self.cluster.populate(1).start()
        [node1] = self.cluster.nodelist()
        session = self.cql_connection(node1, "test")

        session.execute(CREATE_USER_TABLE)
        session.execute("INSERT INTO users (user_name, password, gender, state, birth_year) VALUES('frodo', 'pass@', 'male', 'CA', 1985);")

        node1.flush()
        node1.compact()
        sstable = node1.get_sstables("test", "users")[0]

        tempf = NamedTemporaryFile(delete=False)
        tempf.write(CREATE_USER_TABLE)
        tempf.flush()
        output = sh(["java", "-jar", self.uberjar_location, "toJson", sstable, "-c", tempf.name, "-e"])
        print output
        self.assertEqual(json.loads(output), [[{"name": "user_name", "value": "frodo"}]])

def get_partition(name, result):
    for p in result:
        if p['partition']['key'] == name:
            return p
        elif isinstance(p['partition']['key'], type({})):
            for key in p['partition']['key']:
                if key['name'] == name:
                    return p
    return None

class ToJson(IntegrationTest):
    def __init__(self, methodName='runTest'):
        TestCase.__init__(self, methodName)
        self.name = 'ToJson'

    def test_composite(self):
        self.cluster.populate(1).start()
        [node1] = self.cluster.nodelist()
        session = self.cql_connection(node1, "test")
        session.execute(COMPOSITE_TABLE)
        session.execute("INSERT INTO composites (key1, key2, ckey1, ckey2, value) VALUES('a', 'b', 'c', 'd', 1);")
        session.execute("INSERT INTO composites (key1, key2, ckey1, ckey2, value) VALUES('e', 'f', 'g', 'h', 2);")

        node1.flush()
        node1.compact()
        sstable = node1.get_sstables("test", "composites")[0]

        output = sh(["java", "-jar", self.uberjar_location, "toJson", sstable])
        print output
        result = json.loads(output)
        self.assertEqual(2, len(result))
        self.assertEqual("a:b", get_partition("a:b", result)['partition']['key'])
        self.assertEqual("e:f", get_partition("e:f", result)['partition']['key'])
        self.assertEqual(1, len(get_partition("a:b", result)['rows']))
        self.assertEqual(['c', 'd'], get_partition("a:b", result)['rows'][0]['clustering'])
        self.assertEqual(['g', 'h'], get_partition("e:f", result)['rows'][0]['clustering'])


    def test_composite_with_schema(self):
        self.cluster.populate(1).start()
        [node1] = self.cluster.nodelist()
        session = self.cql_connection(node1, "test")
        session.execute(COMPOSITE_TABLE)
        session.execute("INSERT INTO composites (key1, key2, ckey1, ckey2, value) VALUES('a', 'b', 'c', 'd', 1);")
        session.execute("INSERT INTO composites (key1, key2, ckey1, ckey2, value) VALUES('e', 'f', 'g', 'h', 2);")

        node1.flush()
        node1.compact()
        sstable = node1.get_sstables("test", "composites")[0]

        tempf = NamedTemporaryFile(delete=False)
        tempf.write(COMPOSITE_TABLE)
        tempf.flush()
        output = sh(["java", "-jar", self.uberjar_location, "toJson", sstable, "-c", tempf.name])
        print output
        result = json.loads(output)
        for p in result:
            del p['rows'][0]['liveness_info']

        self.assertEqual(result,
        [
          {
            "partition" : {
              "key" : [
                { "name" : "key1", "value" : "e" },
                { "name" : "key2", "value" : "f" }
              ]
            },
            "rows" : [
              {
                "type" : "row",
                "clustering" : [
                  { "name" : "ckey1", "value" : "g" },
                  { "name" : "ckey2", "value" : "h" }
                ],
                "cells" : [
                  { "name" : "value", "value" : "2" }
                ]
              }
            ]
          },
          {
            "partition" : {
              "key" : [
                { "name" : "key1", "value" : "a" },
                { "name" : "key2", "value" : "b" }
              ]
            },
            "rows" : [
              {
                "type" : "row",
                "clustering" : [
                  { "name" : "ckey1", "value" : "c" },
                  { "name" : "ckey2", "value" : "d" }
                ],
                "cells" : [
                  { "name" : "value", "value" : "1" },
                ]
              }
            ]
          }
        ])

    def test_simple_single(self):
        self.cluster.populate(1).start()
        [node1] = self.cluster.nodelist()
        session = self.cql_connection(node1, "test")

        session.execute(CREATE_USER_TABLE)
        session.execute("INSERT INTO users (user_name, password, gender, state, birth_year) VALUES('frodo', 'pass@', 'male', 'CA', 1985);")

        node1.flush()
        node1.compact()
        sstable = node1.get_sstables("test", "users")[0]

        tempf = NamedTemporaryFile(delete=False)
        tempf.write(CREATE_USER_TABLE)
        tempf.flush()
        output = sh(["java", "-jar", self.uberjar_location, "toJson", sstable, "-c", tempf.name])
        print output
        result = json.loads(output)
        del result[0]["rows"][0]['liveness_info']
        self.assertEqual({'partition': {'key': [{'name': 'user_name', 'value': 'frodo'}]},
                          'rows': [{
                                   'type': 'row',
                                   'cells': [
                                      {'name': 'birth_year', 'value': '1985'},
                                      {'name': 'gender', 'value': 'male'},
                                      {'name': 'password', 'value': 'pass@'},
                                      {'name': 'state', 'value': 'CA'}]
                                  }]}, result[0])
