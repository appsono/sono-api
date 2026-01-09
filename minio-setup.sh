#!/bin/sh
echo "Waiting for MinIO to be ready..."
until /usr/bin/mc alias set minio http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD; do
  echo "MinIO not ready, waiting..."
  sleep 2
done

echo "MinIO is ready. Creating buckets..."

/usr/bin/mc mb minio/profile-pictures --ignore-existing

/usr/bin/mc mb minio/audio-files --ignore-existing

/usr/bin/mc mb minio/cover-art --ignore-existing

echo "Creating image-only policy for profile pictures..."
cat <<'EOF' >/tmp/image-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::profile-pictures/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::profile-pictures"]
    }
  ]
}
EOF

/usr/bin/mc admin policy create minio image-only-policy /tmp/image-policy.json

echo "Creating audio-files policy..."
cat <<'EOF' >/tmp/audio-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::audio-files/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::audio-files"]
    }
  ]
}
EOF

/usr/bin/mc admin policy create minio audio-files-policy /tmp/audio-policy.json

echo "Setting bucket policy to public read for profile pictures..."
/usr/bin/mc anonymous set public minio/profile-pictures

echo "Setting bucket policy to public read for audio files..."
/usr/bin/mc anonymous set public minio/audio-files

echo "Setting bucket policy to public read for cover art..."
/usr/bin/mc anonymous set public minio/cover-art

echo "MinIO setup complete with both profile-pictures and audio-files buckets."