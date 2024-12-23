import argparse
import pandas as pd
import os
from transformers import LlamaForCausalLM, LlamaTokenizer, AutoTokenizer, AutoModelForCausalLM, LlavaForConditionalGeneration, AutoProcessor
from tqdm import tqdm
from numpy import argmax
import torch
from utils_vl import predict_classification_causal as predict_classification
from utils_vl import predict_classification_causal_by_letter as predict_classification_by_letter

device = "cuda"

def prepare_data(playground,model_name, tokenizer,task):
    if task=="MalayMMLU":
        inputs = []
        outputs = []
        outputs_options = []
        key2id = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
        shot = 0
        data = pd.read_json(f'data/MalayMMLU_{shot}shot.json')
        if playground:
            data = data.iloc[:10]
        for idx, row in data.iterrows():
            ques =  data.iloc[idx]['prompt']


            p = f"Berikut adalah soalan aneka pilihan tentang {row['subject']}. Sila berikan jawapan sahaja.\n\n" + ques + "\nJawapan:" 
            chat = [{"role": "user", "content":[{"type":"text","content": p}]}]
            chat = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)                
            inputs.append(chat)

            idx_label = key2id[row['key']]
            outputs.append(idx_label)
            outputs_options.append(row['options'])
        return inputs, outputs, outputs_options

def prepare_data_few_shot(shot, model_name, tokenizer,task):
    if task == "MalayMMLU":
        inputs = []
        outputs = []
        outputs_options = []
        key2id = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
        data = pd.read_json(f'data/MalayMMLU_{shot}shot.json')

        for i in range(len(data)):
            row = data.iloc[i]
                
            if "llama" in model_name.lower():
                p = data.iloc[i][f'full_question_{shot}shot_llama']
                chat = [{"role": "user", "content": p}]
                chat = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True) +"Jawapan:"
            else:
                p = data.iloc[i][f'full_question_{shot}shot']
                chat = [{"role": "user", "content": p}]
                chat = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
            inputs.append(chat)

            idx_label = key2id[row['key']]
            outputs.append(idx_label)
            outputs_options.append(row['options'])
        return inputs, outputs, outputs_options
            
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--by_letter", 
                        action='store_true', 
                        help="Use this flag to calculate first token accuracy. For calculating full answer accuracy, do not include this flag in args")
    parser.add_argument("--base_model",
                         type=str, 
                         help="Path to pretrained model", 
                         required=True)
    parser.add_argument("--output_folder", 
                        type=str, 
                        default="output",
                        required=True,
                        help="Folder where the output will be saved")
    parser.add_argument("--playground", 
                        type=bool,
                        default=False,
                        help="Set this to True to enable playground mode (default: False).")
    parser.add_argument("--task",
                        type=str, 
                        default="MalayMMLU",
                        help="Specify the task to be executed (default: 'MalayMMLU').")
    parser.add_argument("--shot",
                        type=int, 
                        default=0,
                        help="Provide the number of shots: 0,1,2 or 3")
    parser.add_argument("--token",
                        type=str,
                        help='Specify the HuggingFace token')
    args = parser.parse_args()
    return args


def main():
    args = parse_args()

    os.makedirs(args.output_folder, exist_ok=True)
        

    model_class = LlavaForConditionalGeneration
    SAVE_FILE = f'{args.output_folder}/{args.task}_result_{args.base_model.split("/")[-1]}_{args.by_letter}_{args.shot}shot.csv'
    processor = AutoProcessor.from_pretrained(args.base_model)
  
    model = model_class.from_pretrained(args.base_model, token=args.token, torch_dtype=torch.float16, trust_remote_code=True, device_map= "auto")

    model.eval()

    print(args.task)
    
    playground = args.playground # Enable testing of code with only 10 examples of questions
    if args.shot == 0:
        inputs, golds, outputs_options = prepare_data(playground, args.base_model, processor,args.task)
        print(inputs[0])
    else:
        inputs, golds, outputs_options = prepare_data_few_shot(args.shot,args.base_model, processor,args.task)
        print(inputs[0])
    preds = []
    probs = []
    for idx in tqdm(range(len(inputs))):
        if not args.by_letter: # full answer probability
            out = predict_classification(model, processor, inputs[idx], outputs_options[idx], device)
            prob = [o.cpu().detach().item() for o in out] 
            pred = argmax(prob)
            preds.append(pred)

        else: # first token probability
            conf, pred = predict_classification_by_letter(model, processor, inputs[idx], outputs_options[idx], device)
            preds.append(pred)

    output_df = pd.DataFrame()
    output_df['input'] = inputs
    output_df['golds'] = golds
    output_df['options'] = outputs_options
    output_df['preds'] = preds
    print(output_df.iloc[0])
    output_df.to_csv(SAVE_FILE, index=False)

if __name__ == "__main__":
    main()
