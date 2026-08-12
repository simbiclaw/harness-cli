# 营销话术 companion document (CONFLICTING variant, fixture)

## Machine header — trigger_id: keyword1, keyword2, ...
T001: 移动证书, 解锁推荐, 新领
T002: 子证书, 授权领证
T003: 电子营业执照, 年报, 政务网
T004: KEY无法使用, 握奇, 飞天
T005: 招投标, 一个证书
T001: 子证书, 单独领证            # CONFLICT: T001 redefined with different keywords
T002: 移动证书, 新领              # CONFLICT: T002 redefined with different keywords
T003: 授权领证, 子证书            # CONFLICT: T003 redefined with different keywords
T004: 电子营业执照, 解锁          # CONFLICT: T004 redefined with different keywords
T005: 年报, 政务网                # CONFLICT: T005 redefined with different keywords
