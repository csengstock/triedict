# triedict
#
# Copyright (c) 2015 Christian Sengstock, All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.

import unittest
from triedict import TrieDict

class TestTrieDict(unittest.TestCase):

    def test_stats(self):
        triedict = TrieDict()
        self.assertEqual(triedict.size(), 0)
        self.assertEqual(len(triedict), 0)
        self.assertEqual(triedict.num_of_nodes(), 1)
        triedict.add_pattern("abcde", 1)
        self.assertEqual(triedict.size(), 1)
        self.assertEqual(triedict.num_of_nodes(), 6)
        triedict.add_pattern("abcde", 2)
        self.assertEqual(triedict.size(), 1)
        self.assertEqual(triedict.num_of_nodes(), 6)

    def test_get(self):
        triedict = TrieDict()
        strings = ["abc", "bc", "c"]
        for i, s in enumerate(strings):
            triedict.add_pattern(s, i)
        self.assertIsNone(triedict.get(""))
        self.assertIsNone(triedict.get("ab"))
        self.assertIsNone(triedict.get("abcc"))
        self.assertEqual(triedict.get("abc"), 0)
        self.assertEqual(triedict.get("bc"), 1)
        self.assertEqual(triedict.get("c"), 2)
        triedict.add_pattern("abc", 3)
        self.assertEqual(triedict.get("abc"), 3)

    def test_prefix_search(self):
        strings = ["abc", "ab", "a"]
        triedict = TrieDict()
        for i, s in enumerate(strings):
            triedict.add_pattern(s, i+1)
        #print triedict.prefix_search("a")
        matched = triedict.prefix_search("")
        assert len(matched) == 0
        matched = triedict.prefix_search("abc")
        assert len(matched) == 1
        assert matched[0][0] == ""
        assert matched[0][1] == 1
        matched = triedict.prefix_search("a")
        matched.sort(key=lambda x: x[0])
        assert len(matched) == 3
        assert matched[0][0] == ""
        assert matched[0][1] == 3
        assert matched[1][0] == "b"
        assert matched[1][1] == 2
        assert matched[2][0] == "bc"
        assert matched[2][1] == 1

    def test_parse_with_spaces(self):
        triedict = TrieDict()
        patterns = ["this is cool", "cool", "is is cool"]
        for i, s in enumerate(patterns):
            triedict.add_pattern(s, i+1)
        #    0         1         2         3
        #    01234567890123456789012345678901
        s = "yo this is cool is is cool cool!"
        #       this is cool
        #               cool       cool cool
        #                    is is cool
        triedict.generate_suffix_links()
        matched = triedict.parse(s, bound_chars=" !.;,")
        matched.sort(key=lambda x: (x[2],x[0]))
        self.assertEqual(len(matched), 5)
        self.assertEqual(matched[0][0], "cool")
        self.assertEqual(matched[0][2], 14)
        self.assertEqual(matched[1][0], "this is cool")
        self.assertEqual(matched[1][2], 14)
        self.assertEqual(matched[2][0], "cool")
        self.assertEqual(matched[2][2], 25)
        self.assertEqual(matched[3][0], "is is cool")
        self.assertEqual(matched[3][2], 25)
        self.assertEqual(matched[4][0], "cool")
        self.assertEqual(matched[4][2], 30)


    def test_parse_with_bound_chars(self):
        triedict = TrieDict()
        patterns = ["this", "this0", "word", "dude"]
        for i, s in enumerate(patterns):
            triedict.add_pattern(s, i+1)

        #    0         1         2         3
        #    0123456789012345678901234567890123456
        s = "this word...has words dudes, or dude!"
        #    this word                       dude
        #       3    8          9     5         5
        #    this word       word  dude      dude
        triedict.generate_suffix_links()
        matched = triedict.parse(s, bound_chars=" !.;,")
        matched.sort(key=lambda x: x[2])
        self.assertEqual(len(matched), 3)
        self.assertEqual(matched[0][0], "this")
        self.assertEqual(matched[0][2], 3)
        self.assertEqual(matched[1][0], "word")
        self.assertEqual(matched[1][2], 8)
        self.assertEqual(matched[2][0], "dude")
        self.assertEqual(matched[2][2], 35)

        matched = triedict.parse(s, bound_chars=None)
        matched.sort(key=lambda x: x[2])
        self.assertEqual(len(matched), 5)
        self.assertEqual(matched[0][0], "this")
        self.assertEqual(matched[0][2], 3)
        self.assertEqual(matched[1][0], "word")
        self.assertEqual(matched[1][2], 8)
        self.assertEqual(matched[2][0], "word")
        self.assertEqual(matched[2][2], 19)
        self.assertEqual(matched[3][0], "dude")
        self.assertEqual(matched[3][2], 25)
        self.assertEqual(matched[4][0], "dude")
        self.assertEqual(matched[4][2], 35)

    def test_unicode(self):
        triedict = TrieDict()
        s0 = u"aaa aaa"
        a_uc = unichr(257)
        s1 = a_uc+a_uc+a_uc+" "+a_uc+a_uc+a_uc
        s2 = s0 + " " + s1
        triedict.add_pattern(s0)
        triedict.add_pattern(s1)
        triedict.generate_suffix_links()
        matched = triedict.parse(s2)

    # SWITCHED OFF ##################################

    def _test_generate_suffix_pointers(self):
        print "test generate_suffix_pointers..."
        triedict = TrieDict()
        triedict.add_pattern("abcd")
        triedict.add_pattern("bcd")
        triedict.add_pattern("c")
        triedict.generate_suffix_links()
        print triedict
        print triedict.to_string()

    def _test_persist(self):
        triedict = TrieDict()
        triedict.add_pattern("blaaaa")
        triedict.add_pattern("blauu")
        triedict.generate_suffix_links()
        print triedict
        print triedict.to_string()

        triedict.save("test.triedict")

        triedict2 = TrieDict.load("test.triedict")
        print triedict2
        print triedict2.to_string()

    def _test_parse(self):
        triedict = TrieDict()
        patterns = ["abcd", "bcd", "c"]
        for i,s in enumerate(patterns):
            triedict.add_pattern(s, i+1)
        print patterns
        s = "a abcd c bcd"
        print "".join([str(i % 10) for i in xrange(len(s))])
        print s
        try:
            print triedict.parse(s)
            assert False
        except ValueError, e:
            assert True
        triedict.generate_suffix_links()
        print triedict.parse(s)


if __name__ == "__main__":
    unittest.main()