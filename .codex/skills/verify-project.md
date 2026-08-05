# Verify project

1. Chạy `python -m compileall -q apps/helper/src`.
2. Chạy test backend trong `apps/helper`.
3. Chạy `npm test -- --runInBand` và `npm run build` trong `apps/extension`.
4. Kiểm tra `/v1/health` và không có dữ liệu mới trên ổ C.
