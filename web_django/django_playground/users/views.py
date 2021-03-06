from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic import DetailView, ListView, RedirectView, UpdateView
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin

from django.views.decorators.cache import never_cache

from .models import User
from ..services import moves_service
from ..services import utils_service

import logging
from channels import Channel
import json

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        # TODO why not the whole user object ?
        username = User.objects.get(username=self.request.user.username)
        user_is_authenticated = moves_service.is_user_authenticated(username)

        if user_is_authenticated:
            moves_service.validate_authentication(username)
        user = self.request.user

        context = super(UserDetailView, self).get_context_data(**kwargs)
        context['moves_connected'] = user_is_authenticated
        context['moves_auth_url'] = moves_service.get_auth_url()
        context['moves_data_available'] = moves_service.moves_data_available(user)

        return context


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class UserUpdateView(LoginRequiredMixin, UpdateView):

    fields = ['name', ]

    # we already imported User in the view code above, remember?
    model = User

    # send the user back to their own page after a successful update
    def get_success_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})

    def get_object(self):
        # Only get the User record for the user making the request
        return User.objects.get(username=self.request.user.username)


class UserMovesRegisterView(LoginRequiredMixin, SingleObjectMixin, View):
    def get(self, request, *args, **kwargs):
        user = User.objects.get(username=request.user.username)
        if 'code' in request.GET:
            try:
                moves_service.create_auth(request.GET.get('code'), user)
                return redirect('users:detail', username=request.user.username)
            except Exception as e:
                return JsonResponse(e.msg, 400)
        elif 'error' in request.GET:
            return HttpResponse(request.GET, 400)
        else:
            return HttpResponse('Unknown Error', 500)


class UserMovesImportView(LoginRequiredMixin, SingleObjectMixin, View):
    def get(self, request, *args, **kwargs):
        user = User.objects.get(username=request.user.username)
        if moves_service.is_user_authenticated(user):
            try:
                # moves_service.import_storyline(user)
                Channel('background-import-data').send(dict(
                    provider='moves',
                    user_id=user.id
                ))
                return redirect('users:detail', username=user.username)
            except Exception as e:
                return HttpResponse(e.msg, 400)
        else:
            return HttpResponse('Moves Not Authenticated', 400)


class UserListView(LoginRequiredMixin, ListView):
    model = User
    # These next two lines tell the view to index lookups by username
    slug_field = 'username'
    slug_url_kwarg = 'username'


class UserActivityListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        utils_service.hello()
        user = User.objects.get(username=request.user.username)
        summary = moves_service.get_summary_past_days(user, 30)

        for day in summary:
            day['dateObj'] = utils_service.make_date_from(day['date'])
            day['summary'] = utils_service.make_summaries(day)

        moves_profile = user.data_profiles.get(provider='moves')
        using_for = utils_service.get_days_using(moves_profile.data['profile']['firstDate'])
        months = utils_service.get_month_range(moves_profile.data['profile']['firstDate'])

        return render(request, 'pages/list.html', {
            'user': user,
            # 'profile': json.dumps(moves_profile.data, indent=2),
            'profile': moves_profile.data,
            'summary': summary,
            'days': using_for,
            'months': months
        })


class UserActivityMonthView(LoginRequiredMixin, View):
    """return the rendered month template"""
    def get(self, request, date, *args, **kwargs):
        user = User.objects.get(username=request.user.username)

        # cleanup date first
        date = date.replace('/','')

        # get selected month-name & year for month-view
        selMonth = utils_service.get_month_name(date)
        selYear = utils_service.get_year_name(date)

        summary = moves_service.get_summary_month(user, utils_service.make_date_from(date))
        summary.reverse()
        for day in summary:
            day['dateObj'] = utils_service.make_date_from(day['date'])
            day['summary'] = utils_service.make_summaries(day)

        moves_profile = user.data_profiles.get(provider='moves')
        months = utils_service.get_month_range(moves_profile.data['profile']['firstDate'])

        return render(request, 'pages/month.html', {
            'user': user,
            'profile': json.dumps(moves_profile.data, indent=2),
            'summary': summary,
            'months': months,
            'date' : date,
            'sel_month': selMonth,
            'sel_year' : selYear
        })


class UserActivityDetailView(LoginRequiredMixin, View):
    def get(self, request, date, index, *args, **kwargs):
        user = User.objects.get(username=request.user.username)
        api_date = date.replace('-', '')
        activity = moves_service.get_activity_date(user, utils_service.make_date_from(api_date), int(index))

        return render(request, 'pages/detail.html', {
            'user': user,
            'activity': activity,
            'date': date
        })


class UserActivityMapView(LoginRequiredMixin, View):
    def get(self, request, date, *args, **kwargs):
        api_date = date.replace('-', '')
        view_date = utils_service.make_date_from(api_date)
        user = User.objects.get(username=request.user.username)
        activities = moves_service.get_activities_date(user, utils_service.make_date_from(api_date))

        return render(request, 'pages/map.html', {
            'date': date,
            'view_date': view_date,
            'activities': activities
        })


class UserActivityGeoJsonView(LoginRequiredMixin, View):
    def get(self, request, date, *args, **kwargs):
        """returns a json for mapview is called via ajax in map template"""
        api_date = date.replace('-', '')
        utils_service.validate_date(api_date)

        user = User.objects.get(username=request.user.username)
        info = moves_service.get_storyline_date(user, utils_service.make_date_from(api_date))

        features = []
        for segment in info[0]['segments']:
            if segment['type'] == 'place':
                features.append(utils_service.geojson_place(segment))
            elif segment['type'] == 'move':
                features.extend(utils_service.geojson_move(segment))

        geojson = {'type': 'FeatureCollection', 'features': features}
        filename = "moves-%s.geojson" % date
        return HttpResponse(json.dumps(geojson),  content_type='application/geo+json')


class UserActivityMplView(LoginRequiredMixin, View):
    @never_cache
    def get(self, request, date=None, *args, **kwargs):
        """returns a matplot activity image"""

        # init figure & canvas
        plt.close()
        fig = plt.figure()
        fig.patch.set_alpha(0)
        canvas = FigureCanvas(fig)

        # color map for coloring diagram-stuff
        # ref: https://matplotlib.org/examples/color/colormaps_reference.html
        #color_list = plt.cm.tab10(np.linspace(0, 1, 24))

        user = User.objects.get(username=request.user.username)
        if date is not None:
            adjust_date = utils_service.make_date_from(date)
            summary = moves_service.get_summary_month(user, adjust_date)
        else:
            summary = moves_service.get_summary_past_days(user, 30)

        activities = { 1: 'walking', 2: 'running', 3: 'cycling' }
        #print(summary)
        for act in activities:
            x = []
            y = []
            dailydist = {}
            dailydist.clear()
            activity = activities[act]

            for day in summary:

                if not day['summary']:
                    dailydist[day['date']] = 0
                    continue
                for element in day['summary']:
                    if element['activity'] == activity:
                        dailydist[day['date']] = element['distance']

            if dailydist:
                list = sorted(dailydist.items())
                x, y = zip(*list)
                x = [utils_service.make_date_from(key) for key in x]
            else:
                continue

            # do the plotting
            if np.sum(y) > 0:
                plt.plot(x, y, 'o-', color=utils_service.get_activity_color(activity), label=activity)


        # set plot title
        plt.title("Recent Activities", color='white', fontweight='bold')

        # set label for x-axis
        plt.xlabel('Date', labelpad=10, color='white', fontweight='bold')

        # set label for y-axis
        plt.ylabel('Distances (m)', labelpad=10, color='white', fontweight='bold')

        # settings for ticks on x-axis
        plt.xticks(fontsize=10, rotation=33, color='white')
        plt.yticks(fontsize=10, color='white')

        # misc settings
        plt.tick_params('both', color='white')
        plt.subplots_adjust(bottom=0.2, left=0.15)
        plt.grid(True, 'major', 'both', ls='--', lw=.5, c='w', alpha=.25)
        plt.box(False)
        # enable legend
        plt.legend()

        # prepare the response, setting Content-Type
        response=HttpResponse(content_type='image/svg+xml')
        # print the image on the response
        canvas.print_figure(response, format='svg')
        # and return it
        return response


class UserActivityMplDetailView(LoginRequiredMixin, View):
    """returns a matplot activity-detail image"""
    @never_cache
    def get(self, request, date, index, *args, **kwargs):
        user = User.objects.get(username=request.user.username)
        api_date = date.replace('-', '')
        activity = moves_service.get_activity_date(user, utils_service.make_date_from(api_date), int(index))

        # extracting useful data
        currActivity = activity['activity']
        #print(currActivity)
        cutout = activity['trackPoints']

        # color map for coloring diagram-stuff
        # ref: https://matplotlib.org/examples/color/colormaps_reference.html
        # color_list = plt.cm.tab10(np.linspace(0, 1, 24))

        # define what is needed
        speedist = {}
        distance = 0.0
        x = []
        y = []

        # extract data
        for tp in cutout:
            if tp.get('distance') is not None:
                distance += tp.get('distance')
                kmh = tp.get('speed_kmh')
                speedist.update({distance:kmh})

        if speedist:
            list = sorted(speedist.items())
            x, y = zip(*list)

        # set figure dimension
        figsize_w = 9
        figsize_h = 2

        # instantiate the figure
        plt.close()
        fig = plt.figure(figsize=(figsize_w, figsize_h), dpi=300)
        fig.patch.set_alpha(0)
        canvas = FigureCanvas(fig)

        # create some space around axis labels
        plt.subplots_adjust(bottom=0.3, left=0.15)

        # configure plot grid
        plt.grid(True, 'major', 'both', ls='--', lw=.5, c='w', alpha=.25)

        # disable axis box
        plt.box(False)

        # set label for x-axis
        plt.xlabel("Distance (m)", labelpad=10, color='w')

        # set label for y-axis
        plt.ylabel("Velocity (km/h)", labelpad=10, color='w')

        # misc settings
        plt.tick_params('both', color='w')
        plt.xticks(color='w')
        plt.yticks(color='w')

        # create plot or name the shame (no sufficient data)
        if len(x)>0 and len(y)>0:
            plt.plot(x, y, '.-', color=utils_service.get_activity_color(currActivity))
        else:
            fig.text(.25, .5, 'Oops, not enough data for generating a plot :( ', style='normal',
                    bbox={'facecolor': 'red', 'alpha': 0.5, 'pad': 10})

        # prepare the response, setting Content-Type
        response = HttpResponse(content_type='image/svg+xml')
        # print the image on the response
        canvas.print_figure(response, format='svg')
        # and return it
        return response


class UserActivityMplPieView(LoginRequiredMixin, View):

    """returns a matplot pie chart image"""
    @never_cache
    def get(self, request, datepie=None, dayspie=10, *args, **kwargs):
        # init figure & canvas
        fig = plt.figure(figsize=(3,4))
        canvas = FigureCanvas(fig)

        # color map for coloring diagram-stuff
        # ref: https://matplotlib.org/examples/color/colormaps_reference.html
        #color_list = plt.cm.tab10(np.linspace(0, 1, 24))

        user = User.objects.get(username=request.user.username)

        if datepie is not None:
            api_date = datepie.replace('-', '')
            summary = moves_service.get_storyline_date(user, utils_service.make_date_from(api_date))
        else:
            summary = moves_service.get_summary_past_days(user, int(dayspie))

        distances = {'walking':0, 'cycling':0, 'running':0, 'transport':0}

        # get labels and data for the pie
        for key in distances:
            for segments in summary:
                for element in segments['summary']:
                    if element['activity'] == key:
                        distances[key] += element['distance']

        labels = [key for key, value in distances.items() if value > 0]
        sizes = [v for k,v in distances.items() if k in labels]

        # color map for coloring diagram-stuff
        # ref: https://matplotlib.org/examples/color/colormaps_reference.html
        #color_list = plt.cm.tab10(np.linspace(0, 1, 24))

        # init figure & canvas
        plt.close()
        fig = plt.figure(figsize=(3,4))
        fig.patch.set_alpha(0)
        canvas = FigureCanvas(fig)

        # get the colors (wtf ...)
        cols = [utils_service.get_activity_color(label) for label in labels]

        # draw the legend by hand, because display looks shitty for small values (even more wtf ...)
        y = -1.5
        whole = sum(sizes)

        for key in distances.items():
            if key[1] > 0:
                col = utils_service.get_activity_color(key[0])
                legend_activity = str(key[0]) + ": " + str(round(key[1]/(whole/100),2)) + "%"
                plt.text(0.2, y, legend_activity, va='top', ha='right', rotation=0, wrap=True, color=col)
            y+=0.13

        # set pie config
        plt.pie(sizes, labels=None, autopct=None, shadow=True, startangle=90, colors=cols, center=(-0.8,0))

        # misc settings
        plt.subplots_adjust(top=0.3, bottom=0.25)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.tight_layout()
        #plt.legend()

        plt.plot(transparent=True)

        # prepare the response, setting Content-Type
        response = HttpResponse(content_type='image/svg+xml')
        # print the image on the response
        canvas.print_figure(response, format='svg')
        # and return it
        return response


class UserActivityDetailMapView(LoginRequiredMixin, View):
    @never_cache
    def get(self, request, date, index, *args, **kwargs):
        user = User.objects.get(username=request.user.username)
        api_date = date.replace('-', '')
        utils_service.validate_date(api_date)
        activity = moves_service.get_activity_date(user, utils_service.make_date_from(api_date), int(index))
        features = []
        geojson = utils_service.geojson_activity(activity)
        features.append(geojson)
        geojson = {'type': 'FeatureCollection', 'features': features}
        return HttpResponse(json.dumps(geojson),  content_type='application/geo+json')
