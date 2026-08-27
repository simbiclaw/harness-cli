"""Synthesize a minimal llama-arch GGUF with random weights.

M0 asks two questions that do not depend on weight VALUES:
  - does the llama.cpp runtime expose top-k logprobs at a token position (B2.a)
  - decode throughput per call type
A random-weight model answers both honestly. Its scores are meaningless, which
is fine: M0 scores nothing. Weights are seeded so the artifact is reproducible.
"""
import numpy as np, gguf

np.random.seed(0)
n_vocab, n_embd, n_head, n_layer, n_ff, n_ctx = 256, 64, 4, 2, 128, 512
head_dim = n_embd // n_head
OUT = "/home/user/models/tiny-llama-random.gguf"

w = gguf.GGUFWriter(OUT, "llama")
w.add_context_length(n_ctx); w.add_embedding_length(n_embd)
w.add_block_count(n_layer); w.add_feed_forward_length(n_ff)
w.add_head_count(n_head); w.add_head_count_kv(n_head)
w.add_layer_norm_rms_eps(1e-5); w.add_rope_dimension_count(head_dim)
w.add_file_type(gguf.LlamaFileType.ALL_F32)

# Byte-SPM vocab: 256 byte tokens so the high-level completion API can tokenize.
toks = [f"<0x{i:02X}>".encode() for i in range(n_vocab)]
w.add_tokenizer_model("llama")
w.add_token_list(toks)
w.add_token_scores([0.0]*n_vocab)
w.add_token_types([gguf.TokenType.BYTE]*n_vocab)
w.add_bos_token_id(1); w.add_eos_token_id(2); w.add_unk_token_id(0)
w.add_pad_token_id(0)

f32 = lambda *s: np.random.randn(*s).astype(np.float32) * 0.02
w.add_tensor("token_embd.weight", f32(n_vocab, n_embd))
w.add_tensor("output_norm.weight", np.ones(n_embd, np.float32))
w.add_tensor("output.weight", f32(n_vocab, n_embd))
for i in range(n_layer):
    p = f"blk.{i}."
    w.add_tensor(p+"attn_norm.weight", np.ones(n_embd, np.float32))
    w.add_tensor(p+"attn_q.weight", f32(n_embd, n_embd))
    w.add_tensor(p+"attn_k.weight", f32(n_head*head_dim, n_embd))
    w.add_tensor(p+"attn_v.weight", f32(n_head*head_dim, n_embd))
    w.add_tensor(p+"attn_output.weight", f32(n_embd, n_embd))
    w.add_tensor(p+"ffn_norm.weight", np.ones(n_embd, np.float32))
    w.add_tensor(p+"ffn_gate.weight", f32(n_ff, n_embd))
    w.add_tensor(p+"ffn_up.weight", f32(n_ff, n_embd))
    w.add_tensor(p+"ffn_down.weight", f32(n_embd, n_ff))
w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(); w.close()
print("wrote", OUT)
