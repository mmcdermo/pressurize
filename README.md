# pressurize
Scalable machine learning deployment for a collection of pretrained models

## Models and methods
Pressurize models automatically expose their class methods via their API, once those methods are added to `pressurize.json`.

Methods receive a dictionary formed via the JSON request.

## Batching
Pressurize will batch requests to any model method that has a corresponding `batch_{method}` method.

These model methods should expect a dictionary of the form `{requests: [{data: {...}}]}`

### When batching occurs
Batching occurs under two circumstances:
	1) If the current request was received in less than `min_batch_time` milliseconds from the previous request, or
	2) If the number of active requests being served is > `max_batch_size` (or 1 if not provided)

A batch will continue forming until it is either greater than `max_batch_size` or until `max_batch_time` milliseconds has been reached since the first request began being batched.bappl

### How batching
