"""jwt_factory_routes.py - JWT Factory API routes। app.py তে import করুন।"""
from flask import request, jsonify
import jwt_factory as jf

# এটা register_flask(app) হিসেবে call করবে app.py থেকে


def register_jwt_factory(app):
    @app.route('/api/jwtfactory/run', methods=['POST'])
    def jwf_run():
        data = request.get_json(force=True, silent=True) or {}
        res = jf.start_run(
            server_id=data.get('server_id', ''),
            subpath=(data.get('path') or '').strip(),
            source_text=data.get('source') or '',
            output_name=(data.get('output_name') or 'jwt_token.json').strip(),
            region_map_cfg=data.get('regions'),
        )
        if 'error' in res:
            return jsonify(res), 400
        return jsonify(res)

    @app.route('/api/jwtfactory/progress/<run_id>')
    def jwf_progress(run_id):
        r = jf.RUNS.get(run_id)
        if not r:
            return jsonify({'error': 'run not found'}), 404
        return jsonify(r)

    @app.route('/api/jwtfactory/runs')
    def jwf_runs():
        return jsonify({'runs': list(jf.RUNS.values())[-20:]})

    @app.route('/api/jwtfactory/schedules')
    def jwf_list_schedules():
        return jsonify({'schedules': jf.list_schedules()})

    @app.route('/api/jwtfactory/schedules', methods=['POST'])
    def jwf_create_schedule():
        data = request.get_json(force=True, silent=True) or {}
        res = jf.create_schedule(data)
        return (jsonify(res), 400) if 'error' in res else jsonify(res)

    @app.route('/api/jwtfactory/schedules/<sid>', methods=['PUT'])
    def jwf_update_schedule(sid):
        data = request.get_json(force=True, silent=True) or {}
        res = jf.update_schedule(sid, data)
        return (jsonify(res), 400) if 'error' in res else jsonify(res)

    @app.route('/api/jwtfactory/schedules/<sid>', methods=['DELETE'])
    def jwf_delete_schedule(sid):
        return jsonify(jf.delete_schedule(sid))

    @app.route('/api/jwtfactory/schedules/<sid>/action', methods=['POST'])
    def jwf_schedule_action(sid):
        data = request.get_json(force=True, silent=True) or {}
        return jsonify(jf.schedule_action(sid, data.get('action', '')))

    # Scheduler early-init: lazy init on first request (Flask 3 removed before_first_request)
    _init_done = {'v': False}

    def _lazy_init_scheduler():
        if not _init_done['v']:
            _init_done['v'] = True
            jf._init_scheduler()

    @app.before_request
    def _jwf_before():
        _lazy_init_scheduler()

    @app.route('/_jwf_init')
    def _jwf_init():
        jf._init_scheduler()
        return jsonify({'ok': True})
