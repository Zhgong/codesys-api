import unittest
import logging
from pathlib import Path
from src.codesys_api.ironpython_script_engine import IronPythonScriptEngineAdapter

class TestIssue002Repro(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test")
        self.adapter = IronPythonScriptEngineAdapter(
            codesys_path=Path("C:/dummy/codesys.exe"),
            logger=self.logger
        )

    def test_pou_create_should_support_implements(self):
        """测试点 A: 验证 pou/create 生成的脚本是否支持 implements 参数"""
        params = {
            "name": "FB_Test",
            "type": "FunctionBlock",
            "language": "ST",
            "implements": ["I_Action", "I_Status"]
        }
        script = self.adapter._generate_pou_create_script(params)
        
        # 预期的失败：目前的脚本中没有处理 implements 的逻辑
        self.assertIn("IMPLEMENTS I_Action, I_Status", script, "Generated script should contain IMPLEMENTS declaration")

    def test_pou_code_should_handle_full_st_blocks(self):
        """测试点 B: 验证 pou/code 是否能处理带 METHOD 的完整 ST 块"""
        full_code = """FUNCTION_BLOCK FB_Test IMPLEMENTS I_Action
VAR
    x : BOOL;
END_VAR
METHOD DoSomething : BOOL
VAR_INPUT
END_VAR
DoSomething := TRUE;
END_METHOD"""
        params = {
            "path": "FB_Test",
            "code": full_code
        }
        script = self.adapter._generate_pou_code_script(params)
        
        # 目前的脚本可能会直接把这段塞进 implementation 块，导致 CODESYS 报错
        # 我们希望它能检测到这是一个完整块并正确处理
        self.assertIn("METHOD", script)
        self.assertNotIn("textual_implementation.replace(new_text=\"FUNCTION_BLOCK", script, 
                         "Full POU definition should not be treated as simple implementation body")

if __name__ == "__main__":
    unittest.main()
