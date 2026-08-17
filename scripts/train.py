import os
import torch
from datasets import load_dataset
from transformers import TrainingArguments
from trl import SFTTrainer
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, train_on_responses_only

max_seq_length = 2048

# 1. Load Model & Tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-Coder-1.5B-Instruct",
    max_seq_length=max_seq_length,
    load_in_4bit=True,
)

# Apply correct Qwen chat template
tokenizer = get_chat_template(
    tokenizer,
    chat_template="qwen-2.5",
)

# 2. Add LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
)

# 3. Load & Format Dataset
dataset = load_dataset("json", data_files="data/setlhare_train.jsonl", split="train")


def format_prompts(batch):
  texts = [
      tokenizer.apply_chat_template(
          convo, tokenize=False, add_generation_prompt=False
      )
      for convo in batch["messages"]
  ]
  return {"text": texts}


dataset = dataset.map(format_prompts, batched=True)

# 4. Trainer Configuration
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    dataset_num_proc=4,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=150,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        output_dir="outputs",
        report_to="none",
    ),
)

# Mask prompt loss so model trains only on diagnosis/patch/explanation output
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

trainer.train()

# 5. Export Fine-Tuned Model Directly to GGUF Q4_K_M
print("[Setlhare] Exporting fine-tuned model to GGUF Q4_K_M...")
model.save_pretrained_gguf(
    "setlhare_model_gguf", tokenizer, quantization_method="q4_k_m"
)
print("[Setlhare] Training and GGUF export complete!")