"""
Tests for block_structure_factory.py
"""
from nose.plugins.attrib import attr
from unittest import TestCase
from xmodule.modulestore.exceptions import ItemNotFoundError

from ..cache import BlockStructureCache
from ..exceptions import BlockStructureNotFound
from ..factory import BlockStructureFactory
from .helpers import (
    MockCache, MockModulestoreFactory, ChildrenMapTestMixin
)


@attr(shard=2)
class TestBlockStructureFactory(TestCase, ChildrenMapTestMixin):
    """
    Tests for BlockStructureFactory
    """
    def setUp(self):
        super(TestBlockStructureFactory, self).setUp()
        self.children_map = self.SIMPLE_CHILDREN_MAP
        self.modulestore = MockModulestoreFactory.create(self.children_map)

    def test_from_modulestore(self):
        block_structure = BlockStructureFactory.create_from_modulestore(
            root_block_usage_key=0, modulestore=self.modulestore
        )
        self.assert_block_structure(block_structure, self.children_map)

    def test_from_modulestore_fail(self):
        with self.assertRaises(ItemNotFoundError):
            BlockStructureFactory.create_from_modulestore(
                root_block_usage_key=len(self.children_map) + 1,
                modulestore=self.modulestore,
            )

    def test_from_cache(self):
        cache = BlockStructureCache(MockCache())
        block_structure = self.create_block_structure(self.children_map)
        cache.add(block_structure)
        from_cache_block_structure = BlockStructureFactory.create_from_cache(
            block_structure.root_block_usage_key,
            cache,
        )
        self.assert_block_structure(from_cache_block_structure, self.children_map)

    def test_from_cache_none(self):
        cache = BlockStructureCache(MockCache())
        with self.assertRaises(BlockStructureNotFound):
            BlockStructureFactory.create_from_cache(
                root_block_usage_key=0,
                block_structure_cache=cache,
            )

    def test_new(self):
        block_structure = BlockStructureFactory.create_from_modulestore(
            root_block_usage_key=0, modulestore=self.modulestore
        )
        new_structure = BlockStructureFactory.create_new(
            block_structure.root_block_usage_key,
            block_structure._block_relations,  # pylint: disable=protected-access
            block_structure.transformer_data,
            block_structure._block_data_map,  # pylint: disable=protected-access
        )
        self.assert_block_structure(new_structure, self.children_map)
