# Training on Kaggle (free GPU)

End-to-end: SFT (QLoRA) then optional DPO refinement, on a single P100/T4.

## 0. Build the dataset locally

```bash
python scripts/run_pipeline.py --rounds 10 --per-round 20 --dpo 1200
# -> data/generated/sft.jsonl , data/generated/dpo.jsonl
```

Teacher quality caps student quality. For best results set `TEACHER_PROVIDER=deepseek`
(+ `DEEPSEEK_API_KEY`) in `.env` before running; the pipeline works unchanged.

## 1. Upload the dataset to Kaggle

```bash
python scripts/prepare_kaggle_dataset.py --user <your_kaggle_username>
# then run the printed `kaggle datasets create ...` command
```

(Requires the `kaggle` CLI configured with your API token: `~/.kaggle/kaggle.json`.)

## 2. Run `kaggle_sft.ipynb`

1. New Kaggle Notebook, **Accelerator = GPU** (P100 preferred).
2. Add your dataset (`sdx-dataset`) as input; set `SFT_PATH` to `/kaggle/input/sdx-dataset/sft.jsonl`.
3. Run all. It trains QLoRA and saves:
   - LoRA adapter -> `/kaggle/working/adapters/sft`
   - merged fp16 -> `/kaggle/working/merged/sft-fp16`
4. **Session cutoff (12h):** checkpoints save every 100 steps. To resume, save the
   `adapters/sft` output as a new dataset, attach it, and call
   `trainer.train(resume_from_checkpoint=True)`.

## 3. (Optional) Run `kaggle_dpo.ipynb`

1. Save the SFT adapter output as a dataset (`sdx-sft-adapter`) and attach it.
2. Attach the `dpo.jsonl` dataset; set `SFT_ADAPTER` and `DPO_PATH`.
3. Run all -> DPO-refined adapter + merged model in `/kaggle/working/`.

## 4. Export (next phase)

Download `merged/*-fp16`, then convert to GGUF for Ollama and/or push to Hugging Face
(see `deploy/`, built in the deployment phase).

## Config

Hyperparameters mirror `configs/sft.yaml` and `configs/dpo.yaml`; edit the constants
at the top of each notebook to match if you change the YAML.
