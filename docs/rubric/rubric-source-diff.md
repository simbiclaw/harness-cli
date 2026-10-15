# Rubric source diff — `rubric_com_hotline.md` (full) vs `specific-rubric-27.yaml` (abridged)

**Date:** 2026-10-14 · **Full text:** `docs/rubric/rubric_com_hotline.md` (sha256 `73f1f905…`, the
issue #25 attachment, provided by the human) · **Abridged:** `docs/rubric/specific-rubric-27.yaml`
(generated from `simbiclaw/sim` `config/rubric_items.py` @ `0c2cccd`).

## Finding

`specific-rubric-27.yaml` is not a faithful copy of the human rubric. It paraphrases every item,
and in many items it **drops clauses that change what is scored**: exemptions, conjunctions,
auto-pass rules and whitelists. Anything compiled from it, including the 9003/9011 nodes'
`human_version` if they were seeded from it, inherits the losses. **13 items carry an A-impact loss:** 2, 4, 5, 7, 9, 10, 12, 13, 19, 20, 25, 26, 27.

**Recommendation:** make `rubric_com_hotline.md` the authority for `human_version`. Then either
regenerate the yaml from it (the yaml says "regenerate rather than hand-edit", so the fix belongs
in the generator's source) or retire the yaml as a compile input.

## Clauses lost or altered, by impact

**A = changes a verdict.** **B = changes an operator or lexicon.** **C = example only.**

| Item | Lost or altered in yaml | Impact | Consequence |
|---|---|---|---|
| 2 | 支持客服只需能合适的称呼对方，礼貌，不引起对方反感即可 | **A** | Relaxed standard for support agents. Needs an `agent_role` fact (CTI). |
| 2 | 客服问了称谓，但是企业未回答，也不必称呼女士/先生 | **A** | Exempts F1 when the agent asked and got **no answer**, not only when the caller refused. Deterministic: `name_ask ≠ ∅ ∧ customer_self_name = ∅`. |
| 3 | ②③ "地名**和服务点名称**县级及以上需掌握"; ③ "常用的地名、区域和**清晰的**词组" | **B** | Needs a service-point name lexicon. ② (unclear terms) vs ③ (clear terms) separates on whether the customer's term was clear. |
| 4 | "**转接**、候线时长不超过30秒"; 召回语 "X先生/小姐，您好。非常感谢您的耐心等待，您的问题是这样的…"; title "…用语规范**操作正确**" | **A** | The 30 s limit also covers transfer waits. The recall phrase has three parts (称谓 + 您好 + 感谢等待). "操作正确" is not observable from audio (residue). |
| 5 | （不含糊，表达清楚意思即可） | **A** | Closing components are matched **by meaning**, not verbatim: lexicon first, then a judge for paraphrases. |
| 6 | 问题类型/工单状态/服务方式 detail; 服务方式选错不扣分 | B | Still needs ticket-system access. Note the source typo: the fail column reads "工单记录时间为电话挂断后5分钟内". |
| 7 | **当录音质检时，只要能确认客服已将提交所需信息全部都确认清楚了，即可视为通过**（远程：具体问题、qq、企业名称；电话：具体问题、回访电话、姓名、回访时间） | **A** | **Item 7 has a recording-only pass path.** It is compilable from the transcript (a required-field confirmation checklist), not only from the escalation system. See decision D-7. |
| 8 | 市监为"工商"、工商局发证; 出现明显惊讶的语言; "的呢""这个" | B | Larger non-professional-term and filler lexicons. A "surprise" judge is needed. |
| 9 | pass "音量能使客户听清，**不会出现忽高忽低**的情况" (yaml: 音量适当) | **A** | 忽高忽低 attaches to **音量**, which confirms R5: the operator is a level jump, not rate variance. Audibility becomes its own signal (customer says 听不清/大点声). |
| 9 | ③ "电话中**虽未出现抢话**，可是多次出现…略有重叠" | **A** | Confirms R6: Item-9 ③ is the non-competitive overlap class; 抢话 belongs to Item-12. |
| 9 | ④ "**客户语速很慢，客服语速快**，客户表达了'需要慢一点'" | **A** | F4 is a conjunction (customer slow ∧ agent fast ∧ request), not the request alone. |
| 10 | 出现轻微反问句式（支持客服如遇关系紧密的网点除外） | **A** | A new FAIL signal (mild rhetorical question), with a support-agent exemption. Needs `agent_role`. |
| 11 | 处理敷衍; 无精打采 | C | — |
| 12 | 当确实需要时，适当礼貌的打断用户，例如：非常抱歉，打断您一下 | **A** | A polite, needed interruption passes. Confirms the apology mitigation on 插话. |
| 13 | ① "企业描述时间稍长的时候，客服一直非常沉默或当企业呼叫客服的时候未及时回应"; ② "**（当无法判断为客服原因造成时除外）**"; ③ example "发给远程客户的话在电话里说出来" | **A** | ② carries an attribution exemption: repeated questions not attributable to the agent → not a FAIL. "呼叫客服" (喂/在吗) without a timely reply is a deterministic event. |
| 15 | 无法将正确信息快速传达给企业 | C | — |
| 17 | pass: 避免一问一答; 能解释获取对方进度或告知对方进度. fail: 甚至由客户主动与客服人员确认问题; 当企业不配合操作时未能有效引导或转折开去; 不关注客户的理解程度，只顾着自己说 | B | More signals. "只顾着自己说" maps to a talk-ratio measure. |
| 18 | 补充例证: 未确认清楚企业问题，查客服系统发现过期就直接引导延期; 已经连上远程，企业并未要求，客服继续和企业保持通话 | B | Two concrete error-case patterns, candidates for the Error Case Library. |
| 19 | 问题处理完后须建议用户修改密码; 系统填写"以市监审核为准"; 资料审核"以市监要求为准"; 企业概念不清（证书有存储功能）客服未纠正 | **A** | Three **required statements** become checkable as lexicon presence when the context applies. |
| 20 | Scenario → expected-recommendation pairs (旧KEY/无法使用 → 移动证书; 只有一个证书招投标 → 子证书; 年报/政务网多处使用 → 子证书/授权领证; 移动证书 → 授权领证; 电子营业执照登录 → 数字证书; 解锁 → 移动证书 …) | **A** | Item 20 becomes largely a **trigger → expected-response rule table**. NA column also contains a fail-like clause ("…未主动向其引导业务…"), probably misplaced in the source: flag for a human. |
| 22 | Latent-emotion example (认为证书导致电脑无法使用); bad response "这个肯定不是证书造成的" | B | A negative lexicon entry and a trigger pattern. |
| 23 | 例如指导中知道客户之前加过其他客服，多次让客户直接联系别的客服 | B | Concrete deflection pattern. |
| 24 | 答应修改发票邮寄地址却没有提交; 客户反馈APP问题时让企业直接换手机、买手机 | B | Error-case patterns. |
| 25 | （涉及印章定制…可不在电话中说明，但说出口的必须是正确的）（注：凡是…仅仅指导延期、或者咨询网点办理地址、处理业务办理中遇到的问题等，此项均可给1） | **A** | **Auto-pass rules** for whole call classes, plus a scope rule for stamp fees. |
| 26 | 电话起接前、沟通中、挂断后辱骂或骚扰; **多次带有情绪的抢话、压话**; 怪腔怪调，阴阳怪气; 接听私人电话，让企业等一下; 严重质问、反问 | **A** | Overlaps Item-12 (抢话/压话) and Item-10 (反问): a double-penalty partition is needed (X3). Pre-pickup and post-hangup audio is in scope if recorded. |
| 27 | Whitelist adds **证书业务部同事电话**; 未经允许或未按正确流程对外公布网点的业务、财务等信息; 年报验证码: 未核实对方**手机号码和单位名称**、后台查询后直接告诉对方 | **A** | A wider phone whitelist (needs the department's numbers). The verification-code rule needs two confirmations before disclosure. |

Items 1, 14, 16 and 21: the paraphrase loses nothing that changes a verdict.

## Decisions this raises

- **D-7:** compile Item 7's recording-only pass path ("录音质检时…确认清楚即可视为通过")? That would move the scored count from 25 to 26 and changes the product spec's "items 6–7 deferred". Human ruling needed.
- **D-agent_role:** items 2, 10 and 1 (NA) exempt or relax 支持客服. Add `agent_role` (support vs hotline) to the CTI metadata facet (G3).
- **D-20-NA:** the Item-20 NA column contains a fail-like clause. Confirm whether it is a source error.
- **X3:** Item 26 "多次带有情绪的抢话、压话" vs Item 12, and Item 26 "严重质问、反问" vs Item 10 "轻微反问". Partition by severity and emotion so one event is not penalised twice.
