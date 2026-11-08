"""作者：Wangyuan；日期：2026-11-08。职责：通过合成输入复验已确认缺陷。"""
import unittest
from catalog import validate_result
class ReleaseTests(unittest.TestCase):
 def test_string_whitelist_not_substring_authorization(self) -> None:
  with self.assertRaises(ValueError):validate_result({'text':'ok','evidence':['source-1']},'source-10')
