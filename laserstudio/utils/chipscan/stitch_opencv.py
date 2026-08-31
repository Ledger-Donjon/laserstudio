import cv2
from matplotlib import pyplot as plt
import os

dir = "/home/leash/Work/Gits/git.orange.ledgerlabs.net/donjon/charon-eval/pictures/Photoemission/photoemission/20250702_145031"

NX, NY = 4, 4  # Number of images in x and y directions
images = [
    [
        (f"{i}_{j}_ir.png", cv2.imread(os.path.join(dir, f"{i}_{j}_ir.png")))
        for i in range(NX)
    ]
    for j in range(NY)
]
fig, ax = plt.subplots(len(images[0]), len(images), figsize=(14, 10))
for j in range(len(images)):
    for i in range(len(images[j])):
        image = images[NY - i - 1][j]
        ax[i][j].imshow(image[1])
        ax[i][j].set_title(image[0])
        ax[i][j].axis("off")
plt.show()


row_images = []
bw = True
for img_row in images:
    bw = not bw
    for n, im in img_row if bw else img_row[::-1]:
        if im is not None:
            row_images.append(im)


STITCHER_STATUS_DESC = {
    cv2.Stitcher_OK: "Stitching completed successfully.",
    cv2.Stitcher_ERR_NEED_MORE_IMGS: "Not enough images for stitching.",
    cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed.",
    cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera parameters adjustment failed.",
}

# Stitch all images together
print(f"Stitching all {len(row_images)} images together...")

result = row_images[0]  # Start with the first image
for i in range(len(row_images)):
    images = row_images[i : i + 2]
    print(f"Stitching {len(images)} images...")

    stitcher = cv2.Stitcher.create(cv2.Stitcher_SCANS)
    print(
        f"Stitcher created with confidence threshold: {stitcher.panoConfidenceThresh()}"
    )
    stitcher.setPanoConfidenceThresh(
        0.1
    )  # Set a lower confidence threshold for stitching
    status, result = stitcher.stitch(images)
    if status != cv2.Stitcher_OK:
        # Save the two failings images for debugging
        plt.imsave(os.path.join(dir, f"failed_image_{i}.png"), images[0])
        plt.imsave(os.path.join(dir, f"failed_image_{i + 1}.png"), images[1])

        raise RuntimeError(f"Stitching failed: {STITCHER_STATUS_DESC[status]}")
    else:
        print(f"Stitching completed successfully. Current result shape: {result.shape}")
        plt.imsave(os.path.join(dir, f"stitched_image_{i}.png"), result)


# result = row_images[0]  # Start with the first image
# print(f"Initial image shape: {result.shape}")
# for im in row_images[1:]:
#     print("Stitching into the result...")
#     # Stitch the current image into the result
#     stitcher: cv2.Stitcher = cv2.Stitcher_create()
#     status, result = stitcher.stitch(row_images)
#     if status != cv2.Stitcher_OK:
#         raise RuntimeError(f"Stitching failed {STITCHER_STATUS_DESC[status]}")
#     else:
#         print(f"Stitching completed successfully. Current result shape: {result.shape}")
#         plt.imsave(os.path.join(dir, "stitched_image.png"), result)


# stitcher = cv2.Stitcher_create()
# status, stitched_image = stitcher.stitch(all_images)
# if status == cv2.Stitcher_OK:
#     print("Image stitching completed successfully.")
#     plt.imsave(os.path.join(dir, "stitched_image.png"), stitched_image)
#     # Display the stitched image
#     plt.figure(figsize=(14, 10))
#     plt.imshow(stitched_image)
#     plt.title("Stitched image")
#     plt.show()
# elif status == cv2.Stitcher_ERR_NEED_MORE_IMGS:
#     print("Not enough images for stitching.")
# elif status == cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL:
#     print("Homography estimation failed.")
# else:
#     print("Image stitching failed!")


# # print("Stitching rows...")
# # stitched_rows = []
# # for img_row in images:
# #     result = img_row[0][1]  # Start with the first image in the row
# #     for n, im in img_row[1:]:
# #         print(f"Stitching {n} into row...")
# #         # Stitch the current image into the result
# #         stitcher = cv2.Stitcher_create()
# #         status, result = stitcher.stitch((result, im))
# #         if status != cv2.Stitcher_OK:
# #             print(f"Stitching failed for {n} with status {status}")
# #             break
# #     stitched_rows.append(result)

# # fig, ax = plt.subplots(1, len(stitched_rows), figsize=(14, 10))
# # for i in range(len(stitched_rows)):
# #     image = stitched_rows[i]
# #     ax[i].imshow(image)
# #     ax[i].set_title("row " + str(i))
# #     ax[i].axis("off")
# # plt.show()


# # Now stitch the rows together
# print("Stitching rows together...")
# stitcher = cv2.Stitcher_create()
# stitched_image, status = stitcher.stitch(stitched_rows)

# if status == cv2.Stitcher_OK:
#     print("Image stitching completed successfully.")
#     plt.imsave(os.path.join(dir, "stitched_image.png"), stitched_image)
#     # Display the stitched image
#     plt.figure(figsize=(14, 10))
#     plt.imshow(stitched_image)
#     plt.title("Stitched image")
#     plt.show()
# elif status == cv2.Stitcher_ERR_NEED_MORE_IMGS:
#     print("Not enough images for stitching.")
# elif status == cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL:
#     print("Homography estimation failed.")
# else:
#     print("Image stitching failed!")
