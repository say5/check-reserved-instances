apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: ri-monitoring
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      name: ri-monitoring
  template:
    metadata:
      labels:
        name: ri-monitoring
    spec:
      containers:
      - image: say5/ri-monitoring:latest
        imagePullPolicy: Always
        name: reporter
        env:
        - name: DD_METRIC
          value: "ri"
        - name: REPORT_INTERVAL
          value: "7200"
