#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import logging

from os.path import join
from xml.dom.minidom import parseString
from c14n2py import DOMCanonicalizer, Parameters, QNameAwareParameter


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def get_params(param_set_name):
    """ Factory function creates Parameners instance by its name """
    params = Parameters()
    if param_set_name == 'c14nDefault':
        pass
    elif param_set_name == 'c14nComment':
        params.ignoreComments = False
    elif param_set_name == 'c14nTrim':
        params.trimTextNodes = True
    elif param_set_name == 'c14nPrefix':
        params.prefixRewrite = Parameters.SEQUENTIAL
    elif param_set_name == 'c14nQname':
        params.qnameAwareQualifiedAttributes.append(
            QNameAwareParameter(
                "type",
                "http://www.w3.org/2001/XMLSchema-instance"
            )
        )
    elif param_set_name == 'c14nPrefixQname':
        params.prefixRewrite = Parameters.SEQUENTIAL
        params.qnameAwareQualifiedAttributes.append(
            QNameAwareParameter(
                "type",
                "http://www.w3.org/2001/XMLSchema-instance"
            )
        )
    elif param_set_name == 'c14nQnameElem':
        params.qnameAwareElements.append(
            QNameAwareParameter("bar", "http://a")
        )
    elif param_set_name == 'c14nQnameXpathElem':
        params.qnameAwareElements.append(
            QNameAwareParameter("bar", "http://a")
        )
        params.qnameAwareXPathElements.append(
            QNameAwareParameter(
                "IncludedXPath",
                "http://www.w3.org/2010/xmldsig2#"
            )
        )
    elif param_set_name == 'c14nPrefixQnameXpathElem':
        params.prefixRewrite = Parameters.SEQUENTIAL
        params.qnameAwareElements.append(
            QNameAwareParameter("bar", "http://a")
        )
        params.qnameAwareXPathElements.append(
            QNameAwareParameter(
                "IncludedXPath",
                "http://www.w3.org/2010/xmldsig2#"
            )
        )
    else:
        raise NotImplementedError
    return params


class CanonicalizerTest(unittest.TestCase):

    maxDiff = None

    path = './tests/resources/'

    def process_test(self, in_file_name, param_set_name, in_ex_name='',
                     get_include=None, get_exclude=None):
        """ helper function that executes tests """
        with open(join(self.path, '{}.xml'.format(in_file_name)), 'r') as f:
            # Unfornunately xml.dom does not support DTD =(
            doc = parseString(f.read()) 

        if get_exclude:
            exclude_list = get_exclude(doc)
        else:
            exclude_list = None

        if get_include:
            include_list = get_include(doc)
        else:
            include_list = None

        try:
            result = DOMCanonicalizer.canonicalize(
                doc, get_params(param_set_name), include_list, exclude_list
            )
        except Exception as e:
            logger.exception(e)
            result = None

        if in_ex_name:
            ie_suffix = '_{}'.format(in_ex_name)
        else:
            ie_suffix = ''

        reference_file_name = "out_{}_{}{}.xml".format(
            in_file_name, param_set_name, ie_suffix,
        )

        with open(join(self.path, reference_file_name), 'r') as f:
            reference = f.read()

        return result, reference

    def testN2Default(self):
        self.assertEqual(
            *self.process_test('inC14N2', 'c14nDefault')
        )

    def testN2Trim(self):
        self.assertEqual(
            *self.process_test('inC14N2', 'c14nTrim')
        )

    def testN21Default(self):
        self.assertEqual(
            *self.process_test('inC14N2_1', 'c14nDefault')
        )

    def testN21Trim(self):
        self.assertEqual(
            *self.process_test('inC14N2_1', 'c14nTrim')
        )

    def testN3Default(self):
        self.assertEqual(
            *self.process_test('inC14N3', 'c14nDefault')
        )

    def testN3Prefix(self):
        self.assertEqual(
            *self.process_test('inC14N3', 'c14nPrefix')
        )

    def testN3Trim(self):
        self.assertEqual(
            *self.process_test('inC14N3', 'c14nTrim')
        )

    def testN4Default(self):
        self.assertEqual(
            *self.process_test('inC14N4', 'c14nDefault')
        )

    def testN4Trim(self):
        self.assertEqual(
            *self.process_test('inC14N4', 'c14nTrim')
        )

    def testN5Default(self):
        self.assertEqual(
            *self.process_test('inC14N5', 'c14nDefault')
        )

    def testN5Trim(self):
        self.assertEqual(
            *self.process_test('inC14N5', 'c14nTrim')
        )

    def testN6Default(self):
        self.assertEqual(
            *self.process_test('inC14N6', 'c14nDefault')
        )

    def testNsPushdownDefault(self):
        self.assertEqual(
            *self.process_test('inNsPushdown', 'c14nDefault')
        )
    
    def testNsPushdownPrefix(self):
        self.assertEqual(
            *self.process_test('inNsPushdown', 'c14nPrefix')
        )

    def testNsDefaultDefault(self):
        self.assertEqual(
            *self.process_test('inNsDefault', 'c14nDefault')
        )

    def testNsDefaultPrefix(self):
        self.assertEqual(
            *self.process_test('inNsDefault', 'c14nPrefix')
        )

    def testNsSortDefault(self):
        self.assertEqual(
            *self.process_test('inNsSort', 'c14nDefault')
        )

    def testNsSortPrefix(self):
        self.assertEqual(
            *self.process_test('inNsSort', 'c14nPrefix')
        )

    def testNsRedeclDefault(self):
        self.assertEqual(
            *self.process_test('inNsRedecl', 'c14nDefault')
        )
    
    def testNsRedeclPrefix(self):
        self.assertEqual(
            *self.process_test('inNsRedecl', 'c14nPrefix')
        )

    def testNsSuperfluousDefault(self):
        self.assertEqual(
            *self.process_test('inNsSuperfluous', 'c14nDefault')
        )

    def testNsSuperfluousPrefix(self):
        self.assertEqual(
            *self.process_test('inNsSuperfluous', 'c14nPrefix')
        )

    def testNsXmlDefault(self):
        self.assertEqual(
            *self.process_test('inNsXml', 'c14nDefault')
        )

    def testNsXmlPrefix(self):
        self.assertEqual(
            *self.process_test('inNsXml', 'c14nPrefix')
        )

    def testNsXmlQname(self):
        self.assertEqual(
            *self.process_test('inNsXml', 'c14nQname')
        )

    def testNsXmlPrefixQname(self):
        self.assertEqual(
            *self.process_test('inNsXml', 'c14nPrefixQname')
        )

    def testNsContentDefault(self):
        self.assertEqual(
            *self.process_test('inNsContent', 'c14nDefault')
        )
    
    def testNsContentQnameElem(self):
        self.assertEqual(
            *self.process_test('inNsContent', 'c14nQnameElem')
        )

    def testNsContentQnameXpathElem(self):
        self.assertEqual(
            *self.process_test('inNsContent', 'c14nQnameXpathElem')
        )

    def testNsContentPrefixQnameXPathElem(self):
        self.assertEqual(
            *self.process_test('inNsContent', 'c14nPrefixQnameXpathElem')
        )

    def testRC242Default(self):
        self.assertEqual(
            *self.process_test('inRC2_4_2', 'c14nDefault')
        )

    def testN22Trim(self):
        self.assertEqual(
            *self.process_test('inC14N2_2', 'c14nTrim')
        )

    def testWsseDefault(self):
        self.assertEqual(
            *self.process_test('inWsse', 'c14nDefault')
        )

    def testWssePrefix(self):
        self.assertEqual(
            *self.process_test('inWsse', 'c14nPrefix')
        )

    def testN22TrimExcl1(self):

        def excl1(doc):
            n1 = doc.childNodes
            nodes = [
                n1[0].childNodes[3]
            ]
            return nodes

        self.assertEqual(
            *self.process_test('inC14N2_2', 'c14nTrim', 'excl1',
                               get_exclude=excl1)
        )

    def testN22TrimExcl2(self):

        def excl2(doc):
            n1 = doc.childNodes
            dirtynode = n1[0].childNodes[3]
            nodes = [
                dirtynode.attributes.item(0),
                dirtynode.childNodes[0]
            ]
            return nodes

        self.assertEqual(
            *self.process_test('inC14N2_2', 'c14nTrim', 'excl2',
                               get_exclude=excl2)
        )

    def testN3PrefixIncl1(self):

        def incl1(doc):
            n1 = doc.childNodes[1].childNodes
            nodes = [
                # e3
                n1[5],
                # e7
                n1[11].childNodes[1]
            ]
            return nodes

        self.assertEqual(
            *self.process_test('inC14N3', 'c14nPrefix', 'incl1',
                               get_include=incl1)
        )


if __name__ == '__main__':
    unittest.main()
