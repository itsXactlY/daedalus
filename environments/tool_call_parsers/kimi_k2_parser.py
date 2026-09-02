"""
Kimi K2 tool call parser.

Format:
    <|tool_calls_section_begin|>
    <|tool_call_begin|>function_id:0<|tool_call_argument_begin|>{"arg": "val"}<|tool_call_end|>
    <|tool_calls_section_end|>

The function_id format is typically "functions.func_name:index" or "func_name:index".

Based on VLLM's KimiK2ToolParser.extract_tool_calls()
"""

import re
import uuid
from typing import List, Optional

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser


@register_parser("kimi_k2")
class KimiK2ToolCallParser(ToolCallParser):
    """
    Parser for Kimi K2 tool calls.

    Uses section begin/end tokens wrapping individual tool call begin/end tokens.
    The tool_call_id contains the function name (after last dot, before colon).
    """

    START_TOKENS = [
        "<|tool_calls_section_begin|>",
        "<|tool_call_section_begin|>",
    ]

    PATTERN = re.compile(
        r"<\|tool_call_begin\|>\s*(?P<tool_call_id>[^<]+:\d+)\s*"
        r"<\|tool_call_argument_begin\|>\s*"
        r"(?P<function_arguments>(?:(?!<\|tool_call_begin\|>).)*?)\s*"
        r"<\|tool_call_end\|>",
        re.DOTALL,
    )

    def parse(self, text: str) -> ParseResult:
        has_start = any(token in text for token in self.START_TOKENS)
        if not has_start:
            return text, None

        try:
            matches = self.PATTERN.findall(text)
            if not matches:
                return text, None

            tool_calls: List[ChatCompletionMessageToolCall] = []
            for match in matches:
                function_id, function_args = match

                function_name = function_id.split(":")[0].split(".")[-1]

                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=function_id,
                        type="function",
                        function=Function(
                            name=function_name,
                            arguments=function_args.strip(),
                        ),
                    )
                )

            if not tool_calls:
                return text, None

            earliest_start = len(text)
            for token in self.START_TOKENS:
                idx = text.find(token)
                if idx >= 0 and idx < earliest_start:
                    earliest_start = idx

            content = text[:earliest_start].strip()
            return content if content else None, tool_calls

        except Exception:
            return text, None
