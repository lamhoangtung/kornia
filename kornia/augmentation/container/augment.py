import warnings
from itertools import zip_longest
from typing import Any, List, Optional, Tuple, Union, cast

import torch

from kornia.augmentation import GeometricAugmentationBase2D, IntensityAugmentationBase2D, RandomErasing
from kornia.augmentation.base import _AugmentationBase
from kornia.augmentation.container.base import SequentialBase
from kornia.augmentation.container.image import ImageSequential, ParamItem
from kornia.augmentation.container.patch import PatchSequential
from kornia.augmentation.container.utils import ApplyInverse
from kornia.augmentation.container.video import VideoSequential
from kornia.constants import DataKey
from kornia.geometry.boxes import Boxes

__all__ = ["AugmentationSequential"]

AugmentationSequentialInput = Union[
    torch.Tensor, List[torch.Tensor], Tuple[torch.Tensor, torch.Tensor], Tuple[List[torch.Tensor], torch.Tensor]
]


class AugmentationSequential(ImageSequential):
    r"""AugmentationSequential for handling multiple input types like inputs, masks, keypoints at once.

    .. image:: https://kornia-tutorials.readthedocs.io/en/latest/_images/data_augmentation_sequential_5_1.png
        :width: 49 %
    .. image:: https://kornia-tutorials.readthedocs.io/en/latest/_images/data_augmentation_sequential_7_0.png
        :width: 49 %

    Args:
        *args: a list of kornia augmentation modules.
        data_keys: the input type sequential for applying augmentations.
            Accepts "input", "mask", "bbox", "bbox_xyxy", "bbox_xywh", "keypoints".
        same_on_batch: apply the same transformation across the batch.
            If None, it will not overwrite the function-wise settings.
        return_transform: if ``True`` return the matrix describing the transformation
            applied to each. If None, it will not overwrite the function-wise settings.
        keepdim: whether to keep the output shape the same as input (True) or broadcast it
            to the batch form (False). If None, it will not overwrite the function-wise settings.
        random_apply: randomly select a sublist (order agnostic) of args to
            apply transformation.
            If int, a fixed number of transformations will be selected.
            If (a,), x number of transformations (a <= x <= len(args)) will be selected.
            If (a, b), x number of transformations (a <= x <= b) will be selected.
            If True, the whole list of args will be processed as a sequence in a random order.
            If False, the whole list of args will be processed as a sequence in original order.

    .. note::
        Mix augmentations (e.g. RandomMixUp, RandomCutMix) can only be working with "input" data key.
        It is not clear how to deal with the conversions of masks, bounding boxes and keypoints.

    .. note::
        See a working example `here <https://kornia-tutorials.readthedocs.io/en/
        latest/data_augmentation_sequential.html>`__.

    Examples:
        >>> import kornia
        >>> input = torch.randn(2, 3, 5, 6)
        >>> bbox = torch.tensor([[
        ...     [1., 1.],
        ...     [2., 1.],
        ...     [2., 2.],
        ...     [1., 2.],
        ... ]]).expand(2, -1, -1)
        >>> points = torch.tensor([[[1., 1.]]]).expand(2, -1, -1)
        >>> aug_list = AugmentationSequential(
        ...     kornia.augmentation.ColorJitter(0.1, 0.1, 0.1, 0.1, p=1.0),
        ...     kornia.augmentation.RandomAffine(360, p=1.0),
        ...     data_keys=["input", "mask", "bbox", "keypoints"],
        ...     return_transform=False,
        ...     same_on_batch=False,
        ...     random_apply=10,
        ... )
        >>> out = aug_list(input, input, bbox, points)
        >>> [o.shape for o in out]
        [torch.Size([2, 3, 5, 6]), torch.Size([2, 3, 5, 6]), torch.Size([2, 4, 2]), torch.Size([2, 1, 2])]
        >>> # apply the exact augmentation again.
        >>> out_rep = aug_list(input, input, bbox, points, params=aug_list._params)
        >>> [(o == o_rep).all() for o, o_rep in zip(out, out_rep)]
        [tensor(True), tensor(True), tensor(True), tensor(True)]
        >>> # inverse the augmentations
        >>> out_inv = aug_list.inverse(*out)
        >>> [o.shape for o in out_inv]
        [torch.Size([2, 3, 5, 6]), torch.Size([2, 3, 5, 6]), torch.Size([2, 4, 2]), torch.Size([2, 1, 2])]

    This example demonstrates the integration of VideoSequential and AugmentationSequential.

        >>> import kornia
        >>> input = torch.randn(2, 3, 5, 6)[None]
        >>> bbox = torch.tensor([[
        ...     [1., 1.],
        ...     [2., 1.],
        ...     [2., 2.],
        ...     [1., 2.],
        ... ]]).expand(2, -1, -1)[None]
        >>> points = torch.tensor([[[1., 1.]]]).expand(2, -1, -1)[None]
        >>> aug_list = AugmentationSequential(
        ...     VideoSequential(
        ...         kornia.augmentation.ColorJitter(0.1, 0.1, 0.1, 0.1, p=1.0),
        ...         kornia.augmentation.RandomAffine(360, p=1.0),
        ...     ),
        ...     data_keys=["input", "mask", "bbox", "keypoints"]
        ... )
        >>> out = aug_list(input, input, bbox, points)
        >>> [o.shape for o in out]
        [torch.Size([1, 2, 3, 5, 6]), torch.Size([1, 2, 3, 5, 6]), torch.Size([1, 2, 4, 2]), torch.Size([1, 2, 1, 2])]

    Perform ``OneOf`` transformation with ``random_apply=1`` and ``random_apply_weights`` in ``AugmentationSequential``.

        >>> import kornia
        >>> input = torch.randn(2, 3, 5, 6)[None]
        >>> bbox = torch.tensor([[
        ...     [1., 1.],
        ...     [2., 1.],
        ...     [2., 2.],
        ...     [1., 2.],
        ... ]]).expand(2, -1, -1)[None]
        >>> points = torch.tensor([[[1., 1.]]]).expand(2, -1, -1)[None]
        >>> aug_list = AugmentationSequential(
        ...     VideoSequential(
        ...         kornia.augmentation.RandomAffine(360, p=1.0),
        ...     ),
        ...     VideoSequential(
        ...         kornia.augmentation.ColorJitter(0.1, 0.1, 0.1, 0.1, p=1.0),
        ...     ),
        ...     data_keys=["input", "mask", "bbox", "keypoints"],
        ...     random_apply=1,
        ...     random_apply_weights=[0.5, 0.3]
        ... )
        >>> out = aug_list(input, input, bbox, points)
        >>> [o.shape for o in out]
        [torch.Size([1, 2, 3, 5, 6]), torch.Size([1, 2, 3, 5, 6]), torch.Size([1, 2, 4, 2]), torch.Size([1, 2, 1, 2])]
    """

    def __init__(
        self,
        *args: Union[_AugmentationBase, ImageSequential],
        data_keys: List[Union[str, int, DataKey]] = [DataKey.INPUT],
        same_on_batch: Optional[bool] = None,
        return_transform: Optional[bool] = None,
        keepdim: Optional[bool] = None,
        random_apply: Union[int, bool, Tuple[int, int]] = False,
        random_apply_weights: Optional[List[float]] = None,
    ) -> None:
        super().__init__(
            *args,
            same_on_batch=same_on_batch,
            return_transform=return_transform,
            keepdim=keepdim,
            random_apply=random_apply,
            random_apply_weights=random_apply_weights,
        )

        self.data_keys = [DataKey.get(inp) for inp in data_keys]

        if not all(in_type in DataKey for in_type in self.data_keys):
            raise AssertionError(f"`data_keys` must be in {DataKey}. Got {data_keys}.")

        if self.data_keys[0] != DataKey.INPUT:
            raise NotImplementedError(f"The first input must be {DataKey.INPUT}.")

        self.contains_video_sequential: bool = False
        for arg in args:
            if isinstance(arg, PatchSequential) and not arg.is_intensity_only():
                warnings.warn("Geometric transformation detected in PatchSeqeuntial, which would break bbox, mask.")
            if isinstance(arg, VideoSequential):
                self.contains_video_sequential = True

    def inverse(  # type: ignore
        self,
        *args: torch.Tensor,
        params: Optional[List[ParamItem]] = None,
        data_keys: Optional[List[Union[str, int, DataKey]]] = None,
    ) -> Union[torch.Tensor, List[torch.Tensor]]:
        """Reverse the transformation applied.

        Number of input tensors must align with the number of``data_keys``. If ``data_keys`` is not set, use
        ``self.data_keys`` by default.
        """
        if data_keys is None:
            data_keys = cast(List[Union[str, int, DataKey]], self.data_keys)

        _data_keys: List[DataKey] = [DataKey.get(inp) for inp in data_keys]

        if len(args) != len(data_keys):
            raise AssertionError(
                "The number of inputs must align with the number of data_keys, "
                f"Got {len(args)} and {len(data_keys)}."
            )

        args = self._arguments_preproc(*args, data_keys=_data_keys)

        if params is None:
            if self._params is None:
                raise ValueError(
                    "No parameters available for inversing, please run a forward pass first "
                    "or passing valid params into this function."
                )
            params = self._params

        outputs: List[torch.Tensor] = [None] * len(data_keys)  # type: ignore
        for idx, (arg, dcate) in enumerate(zip(args, data_keys)):
            if dcate == DataKey.INPUT and isinstance(arg, (tuple, list)):
                input, _ = arg  # ignore the transformation matrix whilst inverse
            # Using tensors straight-away
            elif isinstance(arg, (Boxes,)):
                input = arg.data  # all boxes are in (B, N, 4, 2) format now.
            else:
                input = arg
            for (name, module), param in zip_longest(list(self.get_forward_sequence(params))[::-1], params[::-1]):
                if isinstance(module, (_AugmentationBase, ImageSequential)):
                    param = params[name] if name in params else param
                else:
                    param = None
                if isinstance(module, IntensityAugmentationBase2D) and dcate in DataKey \
                        and not isinstance(module, RandomErasing):
                    pass  # Do nothing
                elif isinstance(module, ImageSequential) and module.is_intensity_only() and dcate in DataKey:
                    pass  # Do nothing
                elif isinstance(module, VideoSequential) and dcate not in [DataKey.INPUT, DataKey.MASK]:
                    batch_size: int = input.size(0)
                    input = input.view(-1, *input.shape[2:])
                    input = ApplyInverse.inverse_by_key(input, module, param, dcate)
                    input = input.view(batch_size, -1, *input.shape[1:])
                elif isinstance(module, PatchSequential):
                    raise NotImplementedError("Geometric involved PatchSequential is not supported.")
                elif isinstance(module, (GeometricAugmentationBase2D, ImageSequential, RandomErasing)) \
                        and dcate in DataKey:
                    input = ApplyInverse.inverse_by_key(input, module, param, dcate)
                elif isinstance(module, (SequentialBase,)):
                    raise ValueError(f"Unsupported Sequential {module}.")
                else:
                    raise NotImplementedError(f"data_key {dcate} is not implemented for {module}.")
            if isinstance(arg, (Boxes,)):
                arg._data = input
                outputs[idx] = arg.to_tensor()
            else:
                outputs[idx] = input

        if len(outputs) == 1 and isinstance(outputs, (tuple, list)):
            return outputs[0]

        return outputs

    def __packup_output__(  # type: ignore
        self, output: List[AugmentationSequentialInput], label: Optional[torch.Tensor] = None
    ) -> Union[
        AugmentationSequentialInput,
        Tuple[AugmentationSequentialInput, Optional[torch.Tensor]],
        List[AugmentationSequentialInput],
        Tuple[List[AugmentationSequentialInput], Optional[torch.Tensor]],
    ]:
        if len(output) == 1 and isinstance(output, (tuple, list)) and self.return_label:
            return output[0], label
        if len(output) == 1 and isinstance(output, (tuple, list)):
            return output[0]
        if self.return_label:
            return output, label
        return output

    def _validate_args_datakeys(self, *args: AugmentationSequentialInput, data_keys: List[DataKey]):
        if len(args) != len(data_keys):
            raise AssertionError(
                f"The number of inputs must align with the number of data_keys. Got {len(args)} and {len(data_keys)}."
            )
        # TODO: validate args batching, and its consistency

    def _arguments_preproc(self, *args: AugmentationSequentialInput, data_keys: List[DataKey]):
        inp: List[Any] = []
        for arg, dcate in zip(args, data_keys):
            if DataKey.get(dcate) in [DataKey.INPUT, DataKey.MASK, DataKey.KEYPOINTS]:
                inp.append(arg)
            elif DataKey.get(dcate) in [DataKey.BBOX, DataKey.BBOX_XYXY, DataKey.BBOX_XYWH]:
                if DataKey.get(dcate) in [DataKey.BBOX]:
                    mode = "vertices_plus"
                elif DataKey.get(dcate) in [DataKey.BBOX_XYXY]:
                    mode = "xyxy"
                elif DataKey.get(dcate) in [DataKey.BBOX_XYWH]:
                    mode = "xywh"
                else:
                    raise ValueError(f"Unsupported mode `{DataKey.get(dcate).name}`.")
                inp.append(Boxes.from_tensor(arg, mode=mode))  # type: ignore
            else:
                raise NotImplementedError(f"input type of {dcate} is not implemented.")
        return inp

    def forward(  # type: ignore
        self,
        *args: AugmentationSequentialInput,
        label: Optional[torch.Tensor] = None,
        params: Optional[List[ParamItem]] = None,
        data_keys: Optional[List[Union[str, int, DataKey]]] = None,
    ) -> Union[
        AugmentationSequentialInput,
        Tuple[AugmentationSequentialInput, Optional[torch.Tensor]],
        List[AugmentationSequentialInput],
        Tuple[List[AugmentationSequentialInput], Optional[torch.Tensor]],
    ]:
        """Compute multiple tensors simultaneously according to ``self.data_keys``."""
        _data_keys: List[DataKey]
        if data_keys is None:
            _data_keys = self.data_keys
        else:
            _data_keys = [DataKey.get(inp) for inp in data_keys]
            self.data_keys = _data_keys
        self._validate_args_datakeys(*args, data_keys=_data_keys)

        args = self._arguments_preproc(*args, data_keys=_data_keys)

        if params is None:
            # image data must exist if params is not provided.
            if DataKey.INPUT in _data_keys:
                _input = args[_data_keys.index(DataKey.INPUT)]
                # If (input, mat) received.
                if isinstance(_input, (tuple,)):
                    inp = _input[0]
                else:
                    inp = _input
                if isinstance(inp, (tuple, list)):
                    raise ValueError(f"`INPUT` should be a tensor but `{type(inp)}` received.")
                # A video input shall be BCDHW while an image input shall be BCHW
                if self.contains_video_sequential:
                    _, out_shape = self.autofill_dim(inp, dim_range=(3, 5))
                else:
                    _, out_shape = self.autofill_dim(inp, dim_range=(2, 4))
                params = self.forward_parameters(out_shape)
            else:
                raise ValueError("`params` must be provided whilst INPUT is not in data_keys.")

        outputs: List[AugmentationSequentialInput] = [None] * len(_data_keys)  # type: ignore
        # Forward the first image data to freeze the parameters.
        if DataKey.INPUT in _data_keys:
            idx = _data_keys.index(DataKey.INPUT)
            _inp = args[idx]
            _out = super().forward(_inp, label, params=params)  # type: ignore
            if self.return_label:
                _input, label = cast(Tuple[AugmentationSequentialInput, torch.Tensor], _out)
            else:
                _input = cast(AugmentationSequentialInput, _out)
            outputs[idx] = _input

        self.return_label = self.return_label or label is not None or self.contains_label_operations(params)

        for idx, (arg, dcate, out) in enumerate(zip(args, _data_keys, outputs)):
            if out is not None:
                continue
            # Using tensors straight-away
            if isinstance(arg, (Boxes,)):
                input = arg.data  # all boxes are in (B, N, 4, 2) format now.
            else:
                input = arg

            for param in params:
                module = self.get_submodule(param.name)
                if dcate == DataKey.INPUT:
                    input, label = self.apply_to_input(input, label, module=module, param=param)
                elif isinstance(module, IntensityAugmentationBase2D) and dcate in DataKey \
                        and not isinstance(module, RandomErasing):
                    pass  # Do nothing
                elif isinstance(module, ImageSequential) and module.is_intensity_only() and dcate in DataKey:
                    pass  # Do nothing
                elif isinstance(module, VideoSequential) and dcate not in [DataKey.INPUT, DataKey.MASK]:
                    batch_size: int = input.size(0)
                    input = input.view(-1, *input.shape[2:])
                    input, label = ApplyInverse.apply_by_key(input, label, module, param, dcate)
                    input = input.view(batch_size, -1, *input.shape[1:])
                elif isinstance(module, PatchSequential):
                    raise NotImplementedError("Geometric involved PatchSequential is not supported.")
                elif isinstance(module, (GeometricAugmentationBase2D, ImageSequential, RandomErasing)) \
                        and dcate in DataKey:
                    input, label = ApplyInverse.apply_by_key(input, label, module, param, dcate)
                elif isinstance(module, (SequentialBase,)):
                    raise ValueError(f"Unsupported Sequential {module}.")
                else:
                    raise NotImplementedError(f"data_key {dcate} is not implemented for {module}.")

            if isinstance(arg, (Boxes,)):
                arg._data = input
                outputs[idx] = arg.to_tensor()
            else:
                outputs[idx] = input

        return self.__packup_output__(outputs, label)
