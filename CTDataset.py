import os
import torch
import SimpleITK as sitk
from torch.utils.data.dataset import Dataset
from torch.utils.data import DataLoader
from multiprocessing import Pool
import os
import json
import numpy as np

class CTDataset(Dataset):
    def __init__(self, CT_image_root, MRI_label_root, transform=None):
        self.CT_path = CT_image_root
        self.MRI_path = MRI_label_root
        self.transform = transform
        self.CT_name = sorted(os.listdir(os.path.join(CT_image_root)))
        self.MRI_name = sorted(os.listdir(os.path.join(MRI_label_root)))

        if os.path.exists('max_dims.json'):
            with open('max_dims.json', 'r') as f:
                print("directly load bounding box dimension")
                self.target_size = tuple(json.load(f))
        else:
            self.target_size = self.compute_target_size()

        if os.path.exists('global_mean_std.json'):
            with open('global_mean_std.json', 'r') as f:
                print("directly load mean and std ")
                stats = json.load(f)
                self.global_mean = stats['mean']
                self.global_std = stats['std']
        else:
            print("Start calculating mean and std for preprocee")
            self.global_mean, self.global_std = self.compute_global_mean_std()
            with open('global_mean_std.json', 'w') as f:
                json.dump({'mean': self.global_mean, 'std': self.global_std}, f)
        

    def compute_global_mean_std(self):
        all_images = []
        for CT_ID in self.CT_name:
            CT_image = sitk.ReadImage(os.path.join(self.CT_path, CT_ID), sitk.sitkFloat32)
            target_size = self.target_size
            start_index_CT = [(orig_dim - target_dim) // 2 for orig_dim, target_dim in zip(CT_image.GetSize(), target_size)]
            cropped_CT = sitk.RegionOfInterest(CT_image, target_size, start_index_CT)
            CT_array = sitk.GetArrayFromImage(cropped_CT)
            all_images.append(CT_array)
        
        all_images = np.concatenate(all_images, axis=0)  # Concatenate along the depth dimension

        global_mean = float(np.mean(all_images))
        global_std = float(np.std(all_images))
        return global_mean, global_std

    def compute_target_size(self):
         # Find max dimensions across all bounding boxes
        
        if os.path.exists('max_dims.json'):
            with open('max_dims.json', 'w') as f:
                json.dump(max_dims, f)
        else:
            print("failure loading bounding box dim")
            assert False

        return tuple(max_dims)

    def preprocess(self, CT_image, MRI_image):
        # Assuming target_size is in the format (depth, height, width)
        target_size = self.target_size

        # Calculate the starting index for cropping to get a centered crop
        start_index_CT = [(orig_dim - target_dim) // 2 for orig_dim, target_dim in zip(CT_image.GetSize(), target_size)]
        start_index_MRI = [(orig_dim - target_dim) // 2 for orig_dim, target_dim in zip(MRI_image.GetSize(), target_size)]
        
        # Crop both CT and MRI images using the target size
        cropped_CT = sitk.RegionOfInterest(CT_image, target_size, start_index_CT)
        cropped_MRI = sitk.RegionOfInterest(MRI_image, target_size, start_index_MRI)
        
        # Convert to numpy arrays
        CT_array = sitk.GetArrayFromImage(cropped_CT)
        MRI_array = sitk.GetArrayFromImage(cropped_MRI)
        
        # Normalize CT image
        CT_array = (CT_array - self.global_mean) / self.global_std
        
        # Convert to torch tensors
        CT_tensor = torch.FloatTensor(CT_array).unsqueeze(0)  # Adding channel dimension
        MRI_tensor = torch.FloatTensor(MRI_array).unsqueeze(0)  # Adding channel dimension
        
        return CT_tensor, MRI_tensor


    def __getitem__(self, index):
        ############################# We have a bounding box, make sure brain is not larger than bounding box or we need to resize the image
        
        CT_ID = self.CT_name[index]
        MRI_ID = self.MRI_name[index]

        CT_image = sitk.ReadImage(os.path.join(self.CT_path, CT_ID), sitk.sitkFloat32)
        MRI_image = sitk.ReadImage(os.path.join(self.MRI_path, MRI_ID), sitk.sitkFloat32)
        
        CT_tensor, MRI_tensor = self.preprocess(CT_image, MRI_image) 
        
        # If you have additional transformations, apply them here
        if self.transform:
            CT_tensor = self.transform(CT_tensor)
            MRI_tensor = self.transform(MRI_tensor)
        
        
        return CT_ID, MRI_ID, CT_tensor, MRI_tensor

    def __len__(self):
        return len(self.CT_name)


def main():

    print("start working")
    train_set = CTDataset(CT_image_root = "../dataset/images/", MRI_label_root = "../dataset/labels/")
    print(f"dataset length is {len(train_set)}")
    print("data loads fine")
    train_loader = DataLoader(dataset = train_set, batch_size = 1, shuffle=True)
    for CT_ID, MRI_ID, CT_preprocess, MRI_preprocess in train_loader:
        print(f"The ct id is {CT_ID}")
        print(f"The mri id is {MRI_ID}")
        print(f"The shape of MRI preprocess is {CT_preprocess.shape}")
        print(f"max of image is {CT_preprocess.max()}")
        print(f"min of image is {CT_preprocess.min()}")
        print(f"mean is {CT_preprocess.mean()}")
        print(f"ratio of zero and not {torch.sum(CT_preprocess==0)/torch.sum(CT_preprocess!=0)}")
        print(f"max is {MRI_preprocess.max()}")
        print(f"min is {MRI_preprocess.min()}")
        break


if __name__ == "__main__":
    main()