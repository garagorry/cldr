# Custom Image Catalogs

## Overview

A **custom image catalog** is simply a catalog that holds custom images. A custom image is an entry in a custom image catalog that inherits most of its attributes from a source (default) image.

These catalogs and images are typically created to meet an organization's specific **compliance and security requirements** (such as image hardening) or to include custom, **pre-installed software packages**, like monitoring tools or software.

Once configured, these custom catalogs can be used when provisioning new Data Lakes, Cloudera Data Hubs, and environments.

---

## Option 1: Registration via Cloudera Management Console (UI)

### Prerequisites

To create custom catalogs and images, a JSON file accessible from the Cloudera Management Console/Cloudera Control Plane needs to be created following the syntax from the official Cloudera image catalog located at:
`https://cloudbreak-imagecatalog.s3.amazonaws.com/v3-prod-cb-image-catalog.json`

### Registration Steps

To create this custom catalog in the UI:

1. Navigate to **Cloudera Management Console** > **Shared Resources** > **Image Catalogs**.
2. Select **Register Image Catalog**.
3. In the **Image Catalogs / Register** menu, fill in the following details:
   - **Name:** Enter image catalog name
   - **Description:** Please enter the image catalog description
   - **Image Catalog Source:** Please enter the image catalog URL (the location of your hosted JSON file)

---

## Option 2: Creating and Registering Custom Catalogs via CDP CLI

Instead of using the UI, you can use the Cloudera Data Platform (CDP) CLI to fully create and register a custom catalog.

### Prerequisites

If you are replacing the VM images in a custom image entry with a customized version, you must first prepare the image by **modifying an official Cloudera default image**, which you can find in the `cdp-default` catalog. Take note of the image reference, such as the AMI ID.

### Step 1: Find a Source Image

First, identify the ID of the default image you want to use as the base for your custom entry.

```bash
cdp imagecatalog find-default-image --provider <cloud provider> --image-type <image type> --runtime-version <Cloudera Runtime version>
```

### Step 2: Create the Custom Catalog

Next, create an empty custom catalog to hold your new custom image entry.

```bash
cdp imagecatalog create-custom-catalog --catalog-name <unique catalog name> --description "<catalog description>"
```

### Step 3: Set the Custom Image Entry

Register the custom image into the catalog you just created. You will use the source image ID obtained in Step 1 to ensure your custom image inherits the correct default attributes.

```bash
cdp imagecatalog set-runtime-image \
  --catalog-name <unique catalog name> \
  --vm-images region=<region>,imageReference=<custom image ID> \
  --source-image-id <source image ID>
```

_Note: If you are registering a FreeIPA image instead of a Cloudera Runtime image, use the `set-freeipa-image` command instead. During this step, you can also optionally pass the `--base-parcel-url` parameter if you need to override the default Cloudera parcel archive with your own host site._

---

## References

- [Cloudera Data Hub Cluster Planning Guide](https://docs.cloudera.com/data-hub/cloud/cluster-planning/dh-cluster-planning.pdf)
- [Cloudera Data Hub Top Tasks Guide](https://docs.cloudera.com/data-hub/cloud/top-tasks/dh-top-three-tasks.pdf)

```

```
