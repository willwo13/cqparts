import cadquery

from ...utils.geometry import intersect, copy
from ...utils.misc import property_buffered
from . import _casting


class Effect(object):
    """
    An evaluator effect is the conclusion to an evaluation with regard to
    a single solid.

    Effects are sortable (based on proximity to evaluation origin)
    """
    def __init__(self, origin, direction, part, result):
        """
        :param origin: origin of evaluation
        :type  origin: cadquery.Vector
        :param direction: direction of evaluation
        :type  direction: cadquery.Vector
        :param part: effected solid
        :type  part: cadquery.Workplane
        :param result: result of evaluation
        :type  result: cadquery.Workplane
        """
        self.origin = origin
        self.direction = direction.normalized()  # force unit vector
        self.part = part
        self.result = result

    @property
    def start_point(self):
        """
        Start vertex of effect

        :return: vertex
        :rtype: cadquery.Vertex
        """
        edge = self.result.wire().val().Edges()[0]
        return edge.Vertices()[0].Center()

    @property
    def end_point(self):
        edge = self.result.wire().val().Edges()[-1]
        return edge.Vertices()[-1].Center()

    @property
    def origin_displacement(self):
        """
        planar distance of start point from self.origin along self.direction
        """
        return self.start_point.sub(self.origin).dot(self.direction)

    @property
    def wire(self):
        edge = cadquery.Edge.makeLine(self.start_point, self.end_point)
        return cadquery.Wire.assembleEdges([edge])

    @property
    def _wire_wp(self):
        """Put self.wire in it's own workplane for display purposes"""
        return cadquery.Workplane('XY').newObject([self.wire])

    # bool
    def __bool__(self):
        if self.result.edges().objects:
            return True
        return False

    __nonzero__ = __bool__

    # Comparisions
    def __lt__(self, other):
        return self.origin_displacement < other.origin_displacement

    def __le__(self, other):
        return self.origin_displacement <= other.origin_displacement

    def __gt__(self, other):
        return self.origin_displacement > other.origin_displacement

    def __ge__(self, other):
        return self.origin_displacement >= other.origin_displacement


class Evaluator(object):
    """
    An evaluator determines which parts may be effected by a fastener, and how.

    :return: effect on parts (in the order effected)
    :rtype: list of :class:`Effect`

    Can be inherited and modified to perform custom evaluations for
    different fastener types.
    """

    effect_class = Effect

    # Constructor
    def __init__(self, parts, start, dir):
        """
        :param parts: parts involved in fastening
        :type parts: list of :class:`cqparts.Part`
        :param start: fastener starting vertex
        :type start: :class:`cadquery.Vector`
        :param dir: direction fastener is pointing
        :type dir: :class:`cadquery.Vector`
        """
        # cast parameters
        # FIXME: 'solids' should be 'parts' with Part classes
        self.parts = parts
        self.start = _casting.vector(start)
        self.dir = _casting.vector(dir)

        self._evaluation = None

    @property_buffered
    def max_effect_length(self):
        """
        :return: The longest possible effect vector length.
        :rtype: float

        In other words, the *radius* of a sphere:

            - who's center is at ``start``.
            - all ``parts`` are contained within the sphere.
        """
        # Method: using each solid's bounding box:
        #   - get vector from start to bounding box center
        #   - get vector from bounding box center to any corner
        #   - add the length of both vectors
        #   - return the maximum of these from all solids
        def max_length_iter():
            for part in self.parts:
                if part.object.findSolid():
                    bb = part.object.findSolid().BoundingBox()
                    yield bb.center.sub(self.start).Length + (bb.DiagonalLength / 2)
        try:
            return max(max_length_iter())
        except ValueError as e:
            # if iter returns before yielding anything
            return 0

    def perform_evaluation(self):
        # Create effect vector (with max length)
        if not self.max_effect_length:
            # no effect is possible, return an empty list
            return []
        edge = cadquery.Edge.makeLine(
            self.start,
            self.dir.normalized().multiply(self.max_effect_length + 1)  # +1 to avoid rounding errors
        )
        wire = cadquery.Wire.assembleEdges([edge])
        wp = cadquery.Workplane('XY').newObject([wire])

        effect_list = []  # list of self.effect_class instances
        for part in self.parts:
            solid = part.object.translate((0, 0, 0))
            #intersection = solid.intersect(copy(wp))  # FIXME: fix is in cadquery masteria
            intersection = intersect(solid, copy(wp))
            effect = self.effect_class(
                origin=self.start,
                direction=self.dir,
                part=part,
                result=intersection,
            )
            if effect:
                effect_list.append(effect)

        return sorted(effect_list)

    @property
    def eval(self):
        if self._evaluation is None:
            # return buffered evaluation
            self._evaluation = self.perform_evaluation()
        return self._evaluation

    def clear(self):
        self._evaluation = None


class VectorEvaluator(Evaluator):
    # TODO: move vector-specific code from Evaluator into this class
    #       when?, once CylinderEvaluator is complete
    pass


class CylinderEvaluator(Evaluator):
    pass
