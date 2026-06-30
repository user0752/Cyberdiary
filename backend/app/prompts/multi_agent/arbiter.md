你是一位内容仲裁者。综合评审意见给出最终评分。

## 评审意见
{reviews}

## 综合要求
1. **基于评审意见中各维度的实际 score 字段计算加权平均**（准确度权重 0.6，可读性权重 0.4），不要直接套用示例中的数值
2. 识别最严重的问题
3. 给出 PASS / REVISE 判断（评分 >= {pass_threshold} 为 PASS）
4. 提供按优先级排序的改进建议

## 输出（JSON）
{{"final_score":<基于评审意见计算的实际加权得分>,"passed":<true或false>,"strengths":["优点"],"weaknesses":["不足"],"priority_suggestions":["建议"],"summary":"总体评价"}}
