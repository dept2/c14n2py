#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from enum import Enum
from collections import defaultdict
from xml.dom.minidom import Node, Attr
from StringIO import StringIO


logger = logging.getLogger('c14n2py')


class Attribute(object):

    def __init__(self):
        self.uri = None  # type: string
        self.localName = None  # type: string
        self.value = None  # type: string
        self.attributeQualified = True  # type: bool
        self.attrPrfx = None  # type: string
        self.oldPrefix = None  # type: string


class NSDeclaration(object):

    def __init__(self):
        self.uri = None  # type: string
        self.prefix = None  # type: string

    def __eq__(self, other):
        if self is other:
            return True
        if other is None or self.__class__ != other.__class__:
            return False
        if not self.uri is None:
            if self.uri != other.uri:
                return False
        else:
            if not other.uri is None:
                return False
        if not self.prefix is None:
            return self.prefix == other.prefix
        else:
            return other.prefix is None

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        uri_hash = hash(self.uri) if self.uri is not None else 0
        prefix_hash = hash(self.prefix) if self.prefix is not None else 0
        result = 31 * uri_hash + prefix_hash
        return result


class Parameters(object):

    SEQUENTIAL = "sequential"
    NONE = "none"

    def __init__(self):
        self.ignoreComments = True  # type: bool
        self.trimTextNodes = False  # type: bool
        self.prefixRewrite = self.NONE  # type: basestring
        self.qnameAwareQualifiedAttributes = list()  # type: list[QNameAwareParameter]
        self.qnameAwareUnqualifiedAttributes = list()  # type: list[QNameAwareParameter]
        self.qnameAwareElements = list()  # type: list[QNameAwareParameter]
        self.qnameAwareXPathElements = list()  # type: list[QNameAwareParameter]


class PrefixesContainer(object):

    def __init__(self):
        self.prefixMap = defaultdict(list)  # type: dict
        self.prefDefLevel = defaultdict(list)  # type: dict

    def definePrefix(self, firstKey, secondKey, level):
        """
        :param firstKey:
        :type firstKey: string
        :param secondKey:
        :type secondKey: string
        :param level:
        :type level: int
        """
        logger.debug('definePrefix(firstKey={}, secondKey={}, level={}) called'.format(
            firstKey, secondKey, level))
        self.prefixMap[firstKey].append(secondKey)
        self.prefDefLevel[level].append(firstKey)

    def getByFirstKey(self, firstKey):
        """
        :param firstKey:
        :type firstKey: string
        :return:
        :rtype: string
        """
        if self.prefixMap.get(firstKey):
            return self.prefixMap[firstKey][-1]

    def deleteLevel(self, level):
        """
        :param level:
        :type level: int
        """
        if self.prefDefLevel.get(level):
            for firstKey in self.prefDefLevel[level]:
                self.prefixMap[firstKey].pop()
            del self.prefDefLevel[level][:]

    def __str__(self):
        return "map: {}\ndef level: {}".format(self.prefixMap,
                                               self.prefDefLevel)


class QNameAwareParameter(object):

    def __init__(self, name, ns, parentName=None):
        """
        :param name:
        :type name: string
        :param ns:
        :type ns: string
        :param parentName:
        :type parentName: string
        """
        self.name = name  # type: string
        self.ns = ns  # type: string
        self.parentName = parentName  # type: string


class XPathParserStates(Enum):
    COMMON = 1
    SINGLE_QUOTED_STRING = 2
    DOUBLE_QUOTED_STRING = 3
    COLON = 4
    PREFIX = 5


def cmp_ns_by_uri(t0, t1):
    """
    :param t0:
    :type t0: NSDeclaration
    :param t1:
    :type t1: NSDeclaration
    :return:
    :rtype: int
    """
    return cmp(t0.uri, t1.uri)


def cmp_ns_by_prefix(t0, t1):
    """
    :param t0:
    :type t0: NSDeclaration
    :param t1:
    :type t1: NSDeclaration
    :return:
    :rtype: int
    """
    return cmp(t0.prefix, t1.prefix)


class DOMCanonicalizerHandler(object):

    EMPTY_URI = ""  # type: string
    EMPTY_PREFIX = ""  # type: string
    XMLNS = "xmlns"  # type: string
    XML = "xml"  # type: string
    CF = "&#x%s;"  # type: string
    C = ":"  # type: string
    ID_ARRAY_CAPACITY = 20  # type: int
    PREFIX_ARRAY_CAPACITY = 10  # type: int
    PVDNP_MODE = True  # type: bool

    def __init__(self, node, parameters, excludeList, outputBuffer):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        :param parameters:
        :type parameters: Parameters
        :param excludeList:
        :type excludeList: list[xml.dom.minidom.Node]
        :param outputBuffer:
        :type outputBuffer: StringIO.StringIO
        """
        self.excludeList = excludeList  # type: list[xml.dom.minidom.Node]
        self.parameters = parameters  # type: Parameters
        self.outputBuffer = outputBuffer  # type: StringIO.StringIO
        self.nextId = 0  # type: int
        self.redefinedPrefixesMap = dict()  # type: dict
        self.nodeDepth = 0  # type: int
        self.declaredPrefixes = PrefixesContainer()  # type: PrefixesContainer
        self.usedPrefixes = PrefixesContainer()  # type: PrefixesContainer
        self.qNameAwareElements = set()  # type: set
        self.qNameAwareQualifiedAttrs = set()  # type: set
        self.qNameAwareXPathElements = set()  # type: set
        self.qNameAwareUnqualifiedAttrs = set()  # type: set
        self.bSequential = parameters.prefixRewrite == Parameters.SEQUENTIAL  # type: Parameters
        self.tempXpathStorage = None  # type: list
        self.tempPrefixStorage = None  # type: list

        self.loadParentNamespaces(node)
        if self.declaredPrefixes.getByFirstKey("") is None:
            self.declaredPrefixes.definePrefix("", "", 0)

        self.initQNameAwareElements()
        self.initQNameAwareQualifiedAttrs()
        self.initQNameAwareXPathElements()
        self.initQNameAwareUnqualifiedAttrs()

    def initQNameAwareUnqualifiedAttrs(self):
        for en in self.parameters.qnameAwareUnqualifiedAttributes:
            qNameAwareElement = self.createQName(en.ns, en.parentName, en.name)
            self.qNameAwareUnqualifiedAttrs.add(qNameAwareElement)

    def initQNameAwareQualifiedAttrs(self):
        for en in self.parameters.qnameAwareQualifiedAttributes:
            qNameAwareElement = self.createQName(en.ns, en.name)
            self.qNameAwareQualifiedAttrs.add(qNameAwareElement)

    def initQNameAwareXPathElements(self):
        for en in self.parameters.qnameAwareXPathElements:
            qNameAwareElement = self.createQName(en.ns, en.name)
            self.qNameAwareXPathElements.add(qNameAwareElement)

    def createQName(self, uri, localName, attrName=None):
        """
        :param uri:
        :type uri: string
        :param localName:
        :type localName: string
        :param attrName:
        :type attrName: string
        :return:
        :rtype: string
        """
        sb = '{'
        sb += uri or ''
        sb += '}'
        sb += localName
        if attrName is not None:
            sb += '/'
            sb += attrName
        return sb

    def initQNameAwareElements(self):
        for en in self.parameters.qnameAwareElements:
            qNameAwareElement = self.createQName(en.ns, en.name)
            self.qNameAwareElements.add(qNameAwareElement)

    def processElement(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        if self.isInExcludeList(node):
            return
        self.nodeDepth += 1
        self.addNamespaces(node)
        nsDeclarations = set()
        self.evaluateUriVisibility(node, nsDeclarations)
        nsDeclarationList = list()
        nsDeclarationList.extend(nsDeclarations)
        if self.bSequential:
            nsDeclarationList.sort(cmp=cmp_ns_by_uri)
            for nsDeclaration in nsDeclarationList:
                uri = nsDeclaration.uri
                if uri in self.redefinedPrefixesMap:
                    newPrefix = self.redefinedPrefixesMap[uri]
                    nsDeclaration.prefix = newPrefix
                else:
                    nextId = self.nextId
                    self.nextId = nextId + 1
                    newPrefix = 'n' + str(nextId)
                    nsDeclaration.prefix = newPrefix
                    self.redefinedPrefixesMap[uri] = newPrefix
                self.usedPrefixes.definePrefix(nsDeclaration.uri, newPrefix, self.nodeDepth)
        nodeLocalName = self.getLocalName(node)
        nodePrefix = self.getNodePrefix(node)
        nodeUri = self.getNamespaceURIByPrefix(nodePrefix)
        newPrefix = self.getNewPrefix(nodeUri, nodePrefix)
        if newPrefix is None or newPrefix == '':
            self.outputBuffer.write('<%s' % self.getLocalName(node))
        else:
            self.outputBuffer.write('<%s:%s' % (newPrefix, self.getLocalName(node)))

        if not self.PVDNP_MODE or not self.bSequential:
            nsDeclarationList.sort(cmp=cmp_ns_by_prefix)

        for nsDeclaration in nsDeclarationList:
            nsName = nsDeclaration.prefix
            nsUri = nsDeclaration.uri
            if nsName != self.EMPTY_URI:
                self.outputBuffer.write(' %s:%s="%s"' % (self.XMLNS, nsName, nsUri))
            else:
                self.outputBuffer.write(' %s="%s"' % (self.XMLNS, nsUri))

        outAttrsList = self.processAttributes(node, nodeUri)

        for attribute in outAttrsList:
            attrPrfx = attribute.attrPrfx
            attrName = attribute.localName
            attrValue = attribute.value
            if attribute.attributeQualified:
                attrQName = self.createQName(attribute.uri, attribute.localName)
                if attrQName in self.qNameAwareQualifiedAttrs:
                    attrValue = self.processQNameText(attrValue)
            else:
                attrQName = self.createQName(nodeUri, nodeLocalName, attribute.localName)
                if attrQName in self.qNameAwareUnqualifiedAttrs:
                    attrValue = self.processQNameText(attrValue)

            if self.XML == attribute.oldPrefix:
                self.outputBuffer.write(' %s:%s="%s"' % (attribute.oldPrefix, attrName, attrValue))
                continue

            if attrPrfx == '':
                self.outputBuffer.write(' %s="%s"' % (attrName, attrValue))
            else:
                self.outputBuffer.write(' %s:%s="%s"' % (attrPrfx, attrName, attrValue))
        self.outputBuffer.write('>')

    def processQNameText(self, text):
        """
        :param text:
        :type text: string
        :return:
        :rtype: string
        """
        textPrefix = self.getTextPrefix(text)
        textUri = self.getNamespaceURIByPrefix(textPrefix)
        newTextPrefix = self.getNewPrefix(textUri, textPrefix)
        sb = newTextPrefix
        sb += self.C
        sb += text[len(textPrefix)+1:]
        return sb

    def getNewPrefix(self, nodeUri, nodePrefix):
        """
        :param nodeUri:
        :type nodeUri: string
        :param nodePrefix:
        :type nodePrefix: string
        :return:
        :rtype: string
        """
        if self.bSequential:
            return self.usedPrefixes.getByFirstKey(nodeUri)
        else:
            return nodePrefix

    def getNamespaceURIByPrefix(self, prefix):
        """
        :param prefix:
        :type prefix: string
        :return:
        :rtype: string
        """
        uri = self.declaredPrefixes.getByFirstKey(prefix)
        if uri is None:
            logger.debug('getNamespaceURIByPrefix({}) uri is None. prefixes: {}'.format(
                prefix, self.declaredPrefixes))
            raise Exception('uri must not be NoneType!')
        return uri

    def cmp_attrs(self, t0, t1):
        """
        :param t0:
        :type t0: Attribute
        :param t1:
        :type t1: Attribute
        :return:
        :rtype: int
        """
        t0Uri = t0.uri if t0.attributeQualified else " "
        t1Uri = t1.uri if t1.attributeQualified else " "
        q0 = self.createQName(t0Uri, t0.localName)
        q1 = self.createQName(t1Uri, t1.localName)
        return cmp(q0, q1)

    def processAttributes(self, node, nodeUri):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        :param nodeUri:
        :type nodeUri: string
        :return:
        :rtype: list[Attribute]
        """
        attributeList = list()
        for ai in range(len(node.attributes)):
            attr = node.attributes.item(ai)
            suffix = self.getLocalName(attr)
            prfxNs = self.getNodePrefix(attr)
            if self.XMLNS == prfxNs:
                continue
            attribute = Attribute()
            attribute.oldPrefix = prfxNs
            attribute.localName = self.getLocalName(attr)
            if self.EMPTY_PREFIX == prfxNs:
                attribute.uri = nodeUri
                attribute.attributeQualified = False
            else:
                if self.XML != prfxNs:
                    attribute.uri = self.getNamespaceURIByPrefix(prfxNs)
                else:
                    attribute.localName = suffix
            attribute.value = self.getAttributeValue(attr.nodeValue)
            if attribute.attributeQualified:
                newPrefix = self.getNewPrefix(attribute.uri, attribute.oldPrefix)
            else:
                newPrefix = ""
            attribute.attrPrfx = newPrefix
            attributeList.append(attribute)
        attributeList.sort(cmp=self.cmp_attrs)
        return attributeList

    def getAttributeValue(self, input):
        """
        :param input:
        :type input: string
        :return:
        :rtype: string
        """
        attrValue = input if input is not None else ""
        attrValue = self.processTextbAttr(attrValue, True)
        value = ''
        for c in attrValue:
            codepoint = ord(c)
            if codepoint == 9 or codepoint == 10 or codepoint == 13:
                value += self.CF % '{:x}'.format(codepoint).upper()
            else:
                value += c
        return value

    def processEndElement(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        if self.isInExcludeList(node):
            return
        nodePrefix = self.getNodePrefix(node)
        nodeUri = self.getNamespaceURIByPrefix(nodePrefix)
        elementPrefix = self.getNewPrefix(nodeUri, nodePrefix)
        if elementPrefix is None or elementPrefix == '':
            self.outputBuffer.write('</%s>' % self.getLocalName(node))
        else:
            self.outputBuffer.write('</%s:%s>' % (elementPrefix, self.getLocalName(node)))
        self.removeNamespaces(node)
        self.nodeDepth -= 1

    def processText(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        text = node.nodeValue if node.nodeValue != None else ""
        text = self.processTextbAttr(text, False)
        value = ''
        for c in text:
            codepoint = ord(c)
            if codepoint == 13:
                value += self.CF % '{:x}'.format(codepoint).upper()
            else:
                value += c
        text = value
        if self.parameters.trimTextNodes:
            b = True
            attrs = node.parentNode.attributes
            for ai in range(len(attrs)):
                attr = attrs.item(ai)
                if self.isInExcludeList(attr):
                    continue
                if (self.XML == self.getNodePrefix(attr) and
                        "preserve" == attr.nodeValue and
                        self.getLocalName(attr) == "space"):
                    logger.debug('This node contains preserve space directive')
                    b = False
                    break
            if b:
                text = text.strip()
        element = node.parentNode if node.nodeType == Node.TEXT_NODE else node
        nodePrefix = self.getNodePrefix(element)
        nodeLocalName = self.getLocalName(element)
        nodeUri = self.getNamespaceURIByPrefix(nodePrefix)
        nodeQName = self.createQName(nodeUri, nodeLocalName)
        if nodeQName in self.qNameAwareElements:
            text = self.processQNameText(text)
        if nodeQName in self.qNameAwareXPathElements:
            text = self.processXPathText(text)
        self.outputBuffer.write(text)

    def writeNewXPathCharacter(self, ch, pos):
        """
        :param ch:
        :type ch: int
        :param pos:
        :type pos: int
        :return:
        :rtype: int
        """
        pos -= 1
        if pos < 0:
            # создать новый список заполенный нулями в количестве PREFIX_ARRAY_CAPACITY * 2
            newResultArr = [0 for i in range(self.PREFIX_ARRAY_CAPACITY * 2)]
            # скопировать все элементы из self.tempXpathStorage в новый список в позицию PREFIX_ARRAY_CAPACITY * 2
            newResultArr.extend(self.tempXpathStorage)
            self.tempXpathStorage = newResultArr
            pos += self.PREFIX_ARRAY_CAPACITY * 2
        self.tempXpathStorage[pos] = chr(ch)
        return pos

    def writeXPathPrefix(self, ch, pos):
        """
        :param ch:
        :type ch: int
        :param pos:
        :type pos: int
        :return:
        :rtype: int
        """
        pos -= 1
        if pos < 0:
            newResultArr = [0 for i in range(self.PREFIX_ARRAY_CAPACITY)]
            newResultArr.extend(self.tempPrefixStorage)
            self.tempPrefixStorage = newResultArr
            pos += self.PREFIX_ARRAY_CAPACITY
        self.tempPrefixStorage[pos] = chr(ch)
        return pos

    def processXPathText(self, text):
        """
        :param text:
        :type text: string
        :return:
        :rtype: string
        """
        self.tempXpathStorage = list()
        resultPos = len(text)
        self.tempPrefixStorage = list()
        prefixPos = self.PREFIX_ARRAY_CAPACITY
        state = XPathParserStates.COMMON
        for i in reversed(range(len(text))):
            ch = ord(text[i])
            if state == XPathParserStates.COMMON:
                if ch == ord('\''):
                    state = XPathParserStates.SINGLE_QUOTED_STRING
                elif ch == ord('"'):
                    state = XPathParserStates.DOUBLE_QUOTED_STRING
                elif ch == ord(':'):
                    state = XPathParserStates.COLON
                resultPos = self.writeNewXPathCharacter(ch, resultPos)

            elif state == XPathParserStates.SINGLE_QUOTED_STRING:
                if ch == ord('\''):
                    state = XPathParserStates.COMMON
                resultPos = self.writeNewXPathCharacter(ch, resultPos)

            elif state == XPathParserStates.DOUBLE_QUOTED_STRING:
                if ch == ord('"'):
                    state = XPathParserStates.COMMON
                resultPos = self.writeNewXPathCharacter(ch, resultPos)

            elif state == XPathParserStates.COLON:
                if ch == ord(':'):
                    state = XPathParserStates.COMMON
                    resultPos = self.writeNewXPathCharacter(ch, resultPos)
                    continue
                if self.isNCSymbol(ch):
                    state = XPathParserStates.PREFIX
                    prefixPos = self.writeXPathPrefix(ch, prefixPos)

            elif state == XPathParserStates.PREFIX:
                if self.isNCSymbol(ch):
                    prefixPos = self.writeXPathPrefix(ch, prefixPos)
                else:
                    prefix = ''.join(self.tempPrefixStorage[prefixPos:])
                    prefixPos = len(self.tempPrefixStorage)
                    uri = self.getNamespaceURIByPrefix(prefix)
                    newPrefix = self.getNewPrefix(uri, prefix)
                    for j in reversed(range(len(newPrefix))):
                        newPrefixCh = ord(newPrefix[j])
                        resultPos = self.writeNewXPathCharacter(newPrefixCh, resultPos)
                    if ch == '\'':
                        state = XPathParserStates.SINGLE_QUOTED_STRING
                    elif ch == '"':
                        state = XPathParserStates.DOUBLE_QUOTED_STRING
                    elif ch == ':':
                        state = XPathParserStates.COLON
                    else:
                        state = XPathParserStates.COMMON
                    resultPos = self.writeNewXPathCharacter(ch, resultPos)
        result = ''.join(self.tempXpathStorage[resultPos:])
        return result

    def processPI(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        pass

    def processComment(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        pass

    def processCData(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        self.outputBuffer.write(self.processTextbAttr(node.nodeValue, False))

    def getOutputBlock(self):
        """
        :return:
        :rtype: StringIO.StringIO
        """
        return self.outputBuffer

    def isInExcludeList(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        :return:
        :rtype: bool
        """
        if self.excludeList is not None \
                and node in self.excludeList \
                and (node.nodeType == Node.ELEMENT_NODE or isinstance(node, Attr)) \
                and not (isinstance(node, Attr) and (self.XMLNS == self.getNodePrefix(node) or self.XML == self.getNodePrefix(node))):
            return True
        return False

    def removeNamespaces(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        self.usedPrefixes.deleteLevel(self.nodeDepth)
        self.declaredPrefixes.deleteLevel(self.nodeDepth)

    def evaluateUriVisibility(self, node, nsDeclarations):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        :param nsDeclarations:
        :type nsDeclarations: set[NSDeclaration]
        """
        nodePrf = self.getNodePrefix(node)
        nodeLocalName = self.getLocalName(node)
        nodeUri = self.getNamespaceURIByPrefix(nodePrf)
        self.addNSDeclarationForPrefix(nodePrf, nsDeclarations)
        for ai in range(len(node.attributes)):
            attr = node.attributes.item(ai)
            if self.isInExcludeList(attr):
                continue
            prfx = self.getNodePrefix(attr)
            if self.XMLNS != prfx:
                if self.XML == prfx:
                    continue
                text = self.getAttributeValue(attr.nodeValue)
                if self.EMPTY_PREFIX == prfx:
                    attrNamespaceURI = nodeUri
                    qName = self.createQName(attrNamespaceURI, nodeLocalName, self.getLocalName(attr))
                    self.addVisibilityIfNessesaryByText(qName, text, nsDeclarations, self.qNameAwareUnqualifiedAttrs)
                else:
                    attrNamespaceURI = self.getNamespaceURIByPrefix(prfx)
                    qName = self.createQName(attrNamespaceURI, self.getLocalName(attr))
                    self.addVisibilityIfNessesaryByText(qName, text, nsDeclarations, self.qNameAwareQualifiedAttrs)
                if prfx != '':
                    self.addNSDeclarationForPrefix(prfx, nsDeclarations)
        text = node.nodeValue
        qName = self.createQName(nodeUri, nodeLocalName)
        self.addVisibilityIfNessesaryByText(qName, text, nsDeclarations, self.qNameAwareElements)
        self.addXPathVisibilityIfNessesaryByText(qName, text, nsDeclarations)

    def isNCSymbol(self, ch):
        """
        :param ch:
        :type ch: int
        :return:
        :rtype: bool
        """
        s = chr(ch)
        return s.isalnum() or s == '_' or s == '-' or s == '.'

    def addXPathVisibilityIfNessesaryByText(self, qName, text, nsDeclarations):
        """
        :param qName:
        :type qName: string
        :param text:
        :type text: string
        :param nsDeclarations:
        :type nsDeclarations: set[NSDeclaration]
        """
        if qName in self.qNameAwareXPathElements:
            xPathPrefixes = set()
            state = XPathParserStates.COMMON
            prefixArr = list()
            pos = self.PREFIX_ARRAY_CAPACITY
            for i in reversed(range(len(text))):
                ch = ord(text[i])
                if state == XPathParserStates.COMMON:
                    if ch == ord('\''):
                        state = XPathParserStates.SINGLE_QUOTED_STRING
                    elif ch == ord('"'):
                        state = XPathParserStates.DOUBLE_QUOTED_STRING
                    if ch == ord(':'):
                        state = XPathParserStates.COLON
                elif state == XPathParserStates.SINGLE_QUOTED_STRING:
                    if ch == ord('\''):
                        state = XPathParserStates.COMMON
                elif state == XPathParserStates.DOUBLE_QUOTED_STRING:
                    if ch == ord('"'):
                        state = XPathParserStates.COMMON
                elif state == XPathParserStates.COLON:
                    if ch == ord(':'):
                        state = XPathParserStates.COMMON
                        continue
                    if self.isNCSymbol(ch):
                        state = XPathParserStates.PREFIX
                        pos -= 1
                        if pos < 0:
                            newPrefixArr = [0 for i in range(self.PREFIX_ARRAY_CAPACITY)]
                            newPrefixArr.extend(prefixArr)
                            prefixArr = newPrefixArr
                            pos += self.PREFIX_ARRAY_CAPACITY
                        prefixArr[pos] = chr(ch)
                elif state == XPathParserStates.PREFIX:
                    if self.isNCSymbol(ch):
                        pos -= 1
                        if pos < 0:
                            newPrefixArr = [0 for i in range(self.PREFIX_ARRAY_CAPACITY)]
                            newPrefixArr.extend(prefixArr)
                            prefixArr = newPrefixArr
                            pos += self.PREFIX_ARRAY_CAPACITY
                        prefixArr[pos] = chr(ch)

                    else:
                        prefix = prefixArr[pos:len(prefixArr)]
                        pos = len(prefixArr)
                        xPathPrefixes.add(prefix)
                        if ch == ord('\''):
                            state = XPathParserStates.SINGLE_QUOTED_STRING
                            continue
                        if ch == ord('"'):
                            state = XPathParserStates.DOUBLE_QUOTED_STRING
                            continue
                        if ch == ord(':'):
                            state = XPathParserStates.COLON
                            continue
                        state = XPathParserStates.COMMON
            for prefix in xPathPrefixes:
                self.addNSDeclarationForPrefix(prefix, nsDeclarations)

    def addNSDeclarationForPrefix(self, prefix, nsDeclarations):
        """
        :param prefix:
        :type prefix: string
        :param nsDeclarations:
        :type nsDeclarations: set[NSDeclaration]
        """
        prefixUri = self.getNamespaceURIByPrefix(prefix)
        if self.bSequential:
            if self.usedPrefixes.getByFirstKey(prefixUri) is None:
                nsDeclaration = NSDeclaration()
                nsDeclaration.uri = prefixUri
                nsDeclarations.add(nsDeclaration)
        else:
            existsUri = self.usedPrefixes.getByFirstKey(prefix)
            if existsUri is None and self.EMPTY_PREFIX == prefix and self.EMPTY_URI == prefixUri:
                self.usedPrefixes.definePrefix(prefix, prefixUri, self.nodeDepth)
                return
            if existsUri is None or existsUri != prefixUri:
                self.usedPrefixes.definePrefix(prefix, prefixUri, self.nodeDepth)
                nsDeclaration = NSDeclaration()
                nsDeclaration.uri = prefixUri
                nsDeclaration.prefix = prefix
                nsDeclarations.add(nsDeclaration)

    def addVisibilityIfNessesaryByText(self, checkStr, text, nsDeclarations, checkSet):
        """
        :param checkStr:
        :type checkStr: string
        :param text:
        :type text: string
        :param nsDeclarations:
        :type nsDeclarations: set[NSDeclaration]
        :param checkSet:
        :type checkSet: set[string]
        """
        if checkStr in checkSet:
            prefix = self.getTextPrefix(text)
            if self.XML == prefix:
                return
            self.addNSDeclarationForPrefix(prefix, nsDeclarations)

    def getTextPrefix(self, text):
        """

        :param text:
        :type text: string
        :return:
        :rtype: string
        """
        idx = text.find(self.C)
        prefix = ''
        if idx > -1:
            prefix = text[:idx]
        return prefix

    def addNamespaces(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        for ni in range(len(node.attributes)):
            attr = node.attributes.item(ni)
            if self.isInExcludeList(attr):
                continue
            suffix = self.getLocalName(attr)
            prfxNs = self.getNodePrefix(attr)
            if self.XMLNS == prfxNs:
                uri = attr.nodeValue or ''
                logger.debug('New attrib ns found. uri: %r for attrib %r at depth: %r', uri,
                             suffix, self.nodeDepth)
                self.declaredPrefixes.definePrefix(suffix, uri, self.nodeDepth)
        prfxEl = self.getNodePrefix(node)
        uri = node.namespaceURI or ''
        if prfxEl == '' and uri != '':
            logger.debug('New node ns found. uri: %r for node %r at depth: %r', uri,
                         prfxEl, self.nodeDepth)
            self.declaredPrefixes.definePrefix(prfxEl, uri, self.nodeDepth)

    def processTextbAttr(self, text, bAttr):
        """
        :param text:
        :type text: string
        :param bAttr:
        :type bAttr: bool
        :return:
        :rtype: string
        """
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        if bAttr:
            text = text.replace(">", "&gt;")
        else:
            text = text.replace("\"", "&quot;")
            text = text.replace("#xA", "&#xA;")
            text = text.replace("#x9", "&#x9;")
        text = text.replace("#xD", "&#xD;")
        return text

    def getLocalName(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        :return:
        :rtype: string
        """
        name = node.localName if node.localName is not None else node.nodeName
        if self.XMLNS == name:
            return ''
        idx = name.find(self.C)
        if idx > -1:
            return name[idx+1:]
        return name

    def getNodePrefix(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        :return:
        :rtype: string
        """
        prfx = node.prefix
        if prfx is None or prfx == '':
            prfx = ''
            name = node.nodeName
            if self.XMLNS == name:
                return name
            idx = name.find(self.C)
            if idx > -1:
                return name[:idx]
        return prfx

    def loadParentNamespaces(self, node):
        """
        :param node:
        :type node: xml.dom.minidom.Node
        """
        current = node
        parentNodeList = list()
        while current.parentNode is not None and current.parentNode.nodeType != Node.DOCUMENT_NODE:
            current = current.parentNode
            parentNodeList.append(current)
        depth = 0
        for i in reversed(range(len(parentNodeList))):
            depth += 1
            pnode = parentNodeList[i]
            for ni in range(len(pnode.attributes)):
                attr = pnode.attributes.item(ni)
                suffix = self.getLocalName(attr)
                prfxNs = self.getNodePrefix(attr)
                if self.XMLNS == prfxNs:
                    uri = attr.nodeValue
                    self.declaredPrefixes.definePrefix(suffix, uri, -depth)
        depth += 1
        self.declaredPrefixes.definePrefix("SOAP-ENV", "http://schemas.xmlsoap.org/soap/envelope/", -depth)


def getNodeDepth(node):
    """
    :param node:
    :type node: xml.dom.minidom.Node
    :return:
    :rtype: int
    """
    i = -1
    prnt = node
    while True:
        i += 1
        prnt = prnt.parentNode
        if prnt is None:
            break
    return i


def compare_nodes(n1, n2):
    """
    :param n1:
    :type n1: xml.dom.minidom.Node
    :param n2:
    :type n2: xml.dom.minidom.Node
    :return:
    :rtype: int
    """
    l1 = getNodeDepth(n1)
    l2 = getNodeDepth(n2)
    if l1 != l2:
        return l1 - l2
    else:
        prnt1 = n1.parentNode
        prnt2 = n2.parentNode
        if prnt1 is None:
            return -1
        elif prnt2 is None:
            return 1
        if prnt1 == prnt2:
            nl = prnt1.childNodes
            l1 = -1
            l2 = -1
            for i in range(len(nl)):
                if n1 == nl[i]:
                    l1 = i
                elif n2 == nl[i]:
                    l2 = i
                if l1 != -1 and l2 != -1:
                    break
            return l1 - l2
        else:
            return compare_nodes(prnt1, prnt2)


class DOMCanonicalizer(object):

    def __init__(self, node, includeList, excludeList, params):
        """

        :param node:
        :type node: xml.dom.minidom.Node
        :param includeList:
        :type includeList: list[xml.dom.minidom.Node]
        :param excludeList:
        :type excludeList: list[xml.dom.minidom.Node]
        :param params:
        :type params: Parameters
        """
        self.nodes = list()  # type: list[xml.dom.minidom.Node]
        if node is None:
            raise Exception('node must not be Nontype!')
        if includeList is not None and len(includeList) == 0:
            self.includeList = None  # type: list[xml.dom.minidom.Node]
        else:
            self.includeList = includeList  # type: list[xml.dom.minidom.Node]
        self.node = node  # type: xml.dom.minidom.Node
        sb = StringIO()
        parameters = Parameters() if params is None else params
        excludeList = None if excludeList is not None and len(excludeList) == 0 else excludeList
        self.canonicalizer = DOMCanonicalizerHandler(node, parameters, excludeList, sb)  # type: DOMCanonicalizerHandler

    @staticmethod
    def canonicalize(node, params, includeList=None, excludeList=None):
        return DOMCanonicalizer(node, includeList, excludeList, params).canonicalizeSubTree()

    def canonicalizeSubTree(self):
        if self.includeList is None:
            self.process(self.node)
        else:
            self.processIncludeList()
            while len(self.nodes) > 0:
                self.process(self.nodes[0])
        return self.canonicalizer.getOutputBlock().getvalue()

    def processIncludeList(self):
        allNodes = list()
        for node in self.includeList:
            n = node
            while True:
                if n not in allNodes:
                    allNodes.append(n)
                n = n.getParentNode()
                if n is None:
                    break
        allNodes.sort(cmp=compare_nodes)
        self.nodes = allNodes

    def process(self, node):
        """
        :param node:
        :type node: xml.dom.mimidom.Node
        """
        if self.canonicalizer.isInExcludeList(node):
            return
        nodeType = node.nodeType
        if nodeType == Node.ELEMENT_NODE:
            self.canonicalizer.processElement(node)
        elif nodeType == Node.TEXT_NODE:
            self.canonicalizer.processText(node)
        elif nodeType == Node.PROCESSING_INSTRUCTION_NODE:
            self.canonicalizer.processPI(node)
        elif nodeType == Node.COMMENT_NODE:
            self.canonicalizer.processComment(node)
        elif nodeType == Node.CDATA_SECTION_NODE:
            self.canonicalizer.processCData(node)
        if len(self.nodes) > 0 and node == self.nodes[0]:
            del self.nodes[0]
        if node.hasChildNodes():
            b = len(self.nodes) > 0 and node == self.nodes[0].getParentNode()
            nl = node.childNodes
            for i in range(len(nl)):
                if not b or (len(self.nodes) > 0 and nl.item(i) == self.nodes[0]):
                    self.process(nl.item(i))
        if node.nodeType == Node.ELEMENT_NODE:
            self.canonicalizer.processEndElement(node)
